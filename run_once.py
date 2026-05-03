"""
run_once.py – Chạy 1 lần để check bài mới, dùng cho GitHub Actions
Sử dụng twikit (async) thay cho Nitter RSS
"""
import asyncio
import logging
from telegram import Bot

import config
import storage
import fetcher
import sender

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def main():
    accounts = storage.load_accounts()
    if not accounts:
        logger.info("📭 Không có tài khoản nào trong danh sách.")
        return

    logger.info(f"🔍 Kiểm tra {len(accounts)} tài khoản...")

    seen = storage.load_seen()
    new_posts = await fetcher.fetch_all_accounts(accounts, seen)

    if not new_posts:
        logger.info("✅ Không có bài viết mới.")
        return

    logger.info(f"📨 Gửi {len(new_posts)} bài viết mới...")

    async with Bot(token=config.BOT_TOKEN) as bot:
        await sender.send_posts_batch(bot, new_posts)

    storage.mark_seen([p["id"] for p in new_posts])
    logger.info(f"✅ Xong! Đã gửi {len(new_posts)} bài.")


if __name__ == "__main__":
    asyncio.run(main())
