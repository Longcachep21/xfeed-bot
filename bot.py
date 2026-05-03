"""
bot.py – XFeed Bot: Bot Telegram theo dõi bài viết X
Commands:
  /start   – Giới thiệu bot
  /add     – Thêm tài khoản theo dõi
  /remove  – Xóa tài khoản
  /list    – Xem danh sách đang theo dõi
  /check   – Kiểm tra ngay bài mới
  /status  – Trạng thái bot
  /clear   – Xóa lịch sử đã đọc (check lại từ đầu)
  /help    – Hướng dẫn
"""
import asyncio
import logging
from datetime import datetime

from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.constants import ParseMode

import config
import storage
import fetcher
import sender

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("xfeed.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# ── Biến trạng thái ───────────────────────────────────────────────────────────
bot_start_time = datetime.now()
last_check_time = None
total_sent = 0


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_authorized(update: Update) -> bool:
    """Chỉ cho phép chat_id đã cấu hình."""
    return str(update.effective_chat.id) in [str(c) for c in config.CHAT_IDS]


async def _deny(update: Update):
    await update.message.reply_text("🚫 Bạn không có quyền dùng bot này.")


# ── Commands ──────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return await _deny(update)
    await update.message.reply_text(
        "🐦 <b>XFeed Bot</b> đã khởi động!\n\n"
        "Bot sẽ tự động gửi bài viết mới từ các tài khoản X bạn muốn theo dõi.\n\n"
        "📌 <b>Bắt đầu nhanh:</b>\n"
        "  /add elonmusk – Thêm tài khoản\n"
        "  /check – Kiểm tra ngay\n"
        "  /help – Xem tất cả lệnh",
        parse_mode=ParseMode.HTML,
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return await _deny(update)
    await update.message.reply_text(
        "📖 <b>Hướng dẫn XFeed Bot</b>\n\n"
        "<b>Quản lý tài khoản:</b>\n"
        "  /add &lt;username&gt; – Thêm tài khoản theo dõi\n"
        "  /remove &lt;username&gt; – Xóa tài khoản\n"
        "  /list – Danh sách đang theo dõi\n\n"
        "<b>Kiểm tra bài viết:</b>\n"
        "  /check – Kiểm tra ngay bài mới\n"
        "  /clear – Xóa lịch sử → check lại từ đầu\n\n"
        "<b>Thông tin:</b>\n"
        "  /status – Trạng thái bot\n"
        "  /start – Chào mừng\n\n"
        f"⏱ Bot tự check mỗi <b>{config.CHECK_INTERVAL}</b> phút",
        parse_mode=ParseMode.HTML,
    )


async def cmd_add(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return await _deny(update)

    if not ctx.args:
        await update.message.reply_text(
            "❗ Dùng: /add &lt;username&gt;\nVí dụ: /add elonmusk",
            parse_mode=ParseMode.HTML,
        )
        return

    raw = ctx.args[0]
    # Chấp nhận: elonmusk | @elonmusk | x.com/elonmusk | https://x.com/elonmusk
    raw = raw.strip().lstrip("@")
    if "x.com/" in raw or "twitter.com/" in raw:
        raw = raw.rstrip("/").split("/")[-1]
    username = raw.lower().split("?")[0]  # Bỏ ?s=... nếu có
    if not username.replace("_", "").isalnum():
        await update.message.reply_text("❌ Username không hợp lệ.")
        return

    accounts = storage.load_accounts()
    if len(accounts) >= config.MAX_ACCOUNTS:
        await update.message.reply_text(f"❌ Đã đạt giới hạn {config.MAX_ACCOUNTS} tài khoản.")
        return

    ok = storage.add_account(username)
    if ok:
        await update.message.reply_text(
            f"✅ Đã thêm <b>@{username}</b> vào danh sách theo dõi.\n"
            f"📋 Tổng: {len(storage.load_accounts())} tài khoản",
            parse_mode=ParseMode.HTML,
        )
        logger.info(f"✅ Thêm tài khoản: @{username}")
    else:
        await update.message.reply_text(f"⚠️ <b>@{username}</b> đã có trong danh sách.", parse_mode=ParseMode.HTML)


async def cmd_remove(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return await _deny(update)

    if not ctx.args:
        await update.message.reply_text(
            "❗ Dùng: /remove &lt;username&gt;\nVí dụ: /remove elonmusk",
            parse_mode=ParseMode.HTML,
        )
        return

    username = ctx.args[0].lstrip("@").lower().strip()
    ok = storage.remove_account(username)
    if ok:
        await update.message.reply_text(
            f"🗑 Đã xóa <b>@{username}</b> khỏi danh sách.",
            parse_mode=ParseMode.HTML,
        )
        logger.info(f"🗑 Xóa tài khoản: @{username}")
    else:
        await update.message.reply_text(f"❌ Không tìm thấy <b>@{username}</b>.", parse_mode=ParseMode.HTML)


async def cmd_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return await _deny(update)

    accounts = storage.load_accounts()
    if not accounts:
        await update.message.reply_text(
            "📭 Chưa có tài khoản nào.\nDùng /add &lt;username&gt; để thêm.",
            parse_mode=ParseMode.HTML,
        )
        return

    lines = [f"  {i+1}. <a href='https://x.com/{u}'>@{u}</a>" for i, u in enumerate(accounts)]
    await update.message.reply_text(
        f"📋 <b>Đang theo dõi {len(accounts)} tài khoản:</b>\n\n" + "\n".join(lines),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


async def cmd_check(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global last_check_time, total_sent
    if not _is_authorized(update):
        return await _deny(update)

    accounts = storage.load_accounts()
    if not accounts:
        await update.message.reply_text(
            "📭 Chưa có tài khoản nào.\nDùng /add &lt;username&gt; để thêm.",
            parse_mode=ParseMode.HTML,
        )
        return

    msg = await update.message.reply_text(
        f"🔍 Đang kiểm tra <b>{len(accounts)}</b> tài khoản...",
        parse_mode=ParseMode.HTML,
    )

    seen = storage.load_seen()
    new_posts = await fetcher.fetch_all_accounts(accounts, seen)

    last_check_time = datetime.now()

    if not new_posts:
        await msg.edit_text("✅ Không có bài viết mới.", parse_mode=ParseMode.HTML)
        return

    await msg.edit_text(
        f"📨 Tìm thấy <b>{len(new_posts)}</b> bài mới, đang gửi...",
        parse_mode=ParseMode.HTML,
    )

    await sender.send_posts_batch(ctx.bot, new_posts)

    # Lưu các ID đã gửi
    storage.mark_seen([p["id"] for p in new_posts])
    total_sent += len(new_posts)

    await msg.edit_text(
        f"✅ Đã gửi <b>{len(new_posts)}</b> bài viết mới!",
        parse_mode=ParseMode.HTML,
    )


async def cmd_preset(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Load danh sách tài khoản crypto nổi tiếng có sẵn."""
    if not _is_authorized(update):
        return await _deny(update)

    # Hiển thị menu nếu không có tham số
    if not ctx.args:
        categories = list(storage.CRYPTO_PRESETS.keys())
        lines = []
        for i, cat in enumerate(categories):
            count = len(storage.CRYPTO_PRESETS[cat])
            lines.append(f"  {i+1}. <b>{cat}</b> ({count} kênh)")
        total = sum(len(v) for v in storage.CRYPTO_PRESETS.values())
        await update.message.reply_text(
            f"📋 <b>Danh sách tài khoản Crypto nổi tiếng:</b>\n\n"
            + "\n".join(lines)
            + f"\n\n💡 Dùng <b>/preset all</b> để thêm tất cả <b>{total}</b> tài khoản cùng lúc.",
            parse_mode=ParseMode.HTML,
        )
        return

    if ctx.args[0].lower() == "all":
        added = storage.load_preset()
        total = len(storage.load_accounts())
        await update.message.reply_text(
            f"✅ Đã thêm <b>{added}</b> tài khoản mới.\n"
            f"📊 Tổng đang theo dõi: <b>{total}</b> tài khoản",
            parse_mode=ParseMode.HTML,
        )
    else:
        await update.message.reply_text(
            "❌ Dùng <b>/preset all</b> để thêm tất cả.",
            parse_mode=ParseMode.HTML,
        )


async def cmd_clear(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not _is_authorized(update):
        return await _deny(update)

    import os
    if os.path.exists(config.SEEN_FILE):
        os.remove(config.SEEN_FILE)
    await update.message.reply_text(
        "🧹 Đã xóa lịch sử.\nLần check tới sẽ gửi lại tất cả bài viết gần nhất.",
        parse_mode=ParseMode.HTML,
    )


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global last_check_time, total_sent
    if not _is_authorized(update):
        return await _deny(update)

    accounts  = storage.load_accounts()
    seen_ids  = storage.load_seen()
    uptime    = datetime.now() - bot_start_time
    hours, r  = divmod(int(uptime.total_seconds()), 3600)
    mins      = r // 60

    last_str  = last_check_time.strftime("%H:%M:%S %d/%m") if last_check_time else "Chưa check"

    ids_str = ", ".join(f"<code>{c}</code>" for c in config.CHAT_IDS)
    await update.message.reply_text(
        "📊 <b>Trạng thái XFeed Bot</b>\n\n"
        f"⏱ Uptime: <b>{hours}h {mins}m</b>\n"
        f"👥 Tài khoản theo dõi: <b>{len(accounts)}</b>\n"
        f"📝 Post IDs đã lưu: <b>{len(seen_ids)}</b>\n"
        f"📨 Tổng bài đã gửi: <b>{total_sent}</b>\n"
        f"🔍 Check cuối: <b>{last_str}</b>\n"
        f"⏰ Auto-check: mỗi <b>{config.CHECK_INTERVAL}</b> phút\n"
        f"💬 Chat IDs: {ids_str}\n"
        f"🌐 Nguồn: <code>twikit (X scraper)</code>",
        parse_mode=ParseMode.HTML,
    )


# ── Auto-check Job ────────────────────────────────────────────────────────────

async def auto_check_job(ctx: ContextTypes.DEFAULT_TYPE):
    """Được gọi tự động theo lịch bởi JobQueue."""
    global last_check_time, total_sent

    accounts = storage.load_accounts()
    if not accounts:
        return

    logger.info(f"⏰ Auto-check {len(accounts)} tài khoản...")
    seen = storage.load_seen()
    new_posts = await fetcher.fetch_all_accounts(accounts, seen)
    last_check_time = datetime.now()

    if not new_posts:
        logger.info("✅ Không có bài mới.")
        return

    logger.info(f"📨 Gửi {len(new_posts)} bài mới...")
    await sender.send_posts_batch(ctx.bot, new_posts)
    storage.mark_seen([p["id"] for p in new_posts])
    total_sent += len(new_posts)
    logger.info(f"✅ Đã gửi {len(new_posts)} bài.")


# ── Main ──────────────────────────────────────────────────────────────────────

async def post_init(app: Application):
    """Thiết lập menu lệnh và job schedule sau khi khởi động."""
    await app.bot.set_my_commands([
        BotCommand("start",  "Khởi động bot"),
        BotCommand("preset", "Thêm ngay 30+ kênh crypto nổi tiếng"),
        BotCommand("add",    "Thêm tài khoản X theo dõi"),
        BotCommand("remove", "Xóa tài khoản"),
        BotCommand("list",   "Xem danh sách theo dõi"),
        BotCommand("check",  "Kiểm tra bài viết mới ngay"),
        BotCommand("clear",  "Xóa lịch sử đã đọc"),
        BotCommand("status", "Trạng thái bot"),
        BotCommand("help",   "Hướng dẫn sử dụng"),
    ])

    # Lên lịch auto-check
    interval_secs = config.CHECK_INTERVAL * 60
    app.job_queue.run_repeating(
        auto_check_job,
        interval=interval_secs,
        first=30,  # Check lần đầu sau 30 giây
        name="auto_check",
    )
    logger.info(f"⏰ Auto-check mỗi {config.CHECK_INTERVAL} phút đã được bật.")

    # Thông báo khởi động đến tất cả chats
    for cid in config.CHAT_IDS:
        try:
            await app.bot.send_message(
                chat_id=cid,
                text=(
                    "🚀 <b>XFeed Bot đã khởi động!</b>\n\n"
                    f"⏰ Tự động check mỗi <b>{config.CHECK_INTERVAL}</b> phút\n"
                    f"👥 Đang theo dõi <b>{len(storage.load_accounts())}</b> tài khoản\n\n"
                    "Dùng /help để xem hướng dẫn."
                ),
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            logger.warning(f"Không gửi được tin nhắn khởi động đến {cid}: {e}")


def main():
    logger.info("🐦 XFeed Bot đang khởi động...")

    app = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Đăng ký handlers
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("help",   cmd_help))
    app.add_handler(CommandHandler("preset", cmd_preset))
    app.add_handler(CommandHandler("add",    cmd_add))
    app.add_handler(CommandHandler("remove", cmd_remove))
    app.add_handler(CommandHandler("list",   cmd_list))
    app.add_handler(CommandHandler("check",  cmd_check))
    app.add_handler(CommandHandler("clear",  cmd_clear))
    app.add_handler(CommandHandler("status", cmd_status))

    logger.info("✅ Bot đã sẵn sàng. Nhấn Ctrl+C để dừng.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
