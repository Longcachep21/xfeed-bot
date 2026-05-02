"""
sender.py – Lấy nội dung chính, dịch tiếng Việt, gửi Telegram
Format:
  🐦 @username · 14:30 02/05
  🔗 https://x.com/...
  ─────────────────
  Nội dung chính đã dịch sang tiếng Việt
"""
import re
import asyncio
import logging
from typing import Dict, List

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError
from deep_translator import GoogleTranslator

import config

logger = logging.getLogger(__name__)


def _clean_text(text: str) -> str:
    """Lọc lấy nội dung chính, bỏ rác."""
    # Bỏ URLs
    text = re.sub(r"http\S+", "", text)
    # Bỏ hashtag
    text = re.sub(r"#\w+", "", text)
    # Bỏ @mention
    text = re.sub(r"@\w+", "", text)
    # Bỏ khoảng trắng thừa
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text


def _translate(text: str) -> str:
    """Dịch sang tiếng Việt. Trả về gốc nếu lỗi."""
    if not text or len(text.strip()) < 5:
        return text
    try:
        result = GoogleTranslator(source="auto", target="vi").translate(text[:4500])
        return result if result else text
    except Exception as e:
        logger.warning(f"Loi dich: {e}")
        return text


def _summarize(text: str, max_len: int = 350) -> str:
    """Cắt lấy nội dung chính, không quá max_len ký tự."""
    text = text.strip()
    if len(text) <= max_len:
        return text
    # Cắt ở cuối câu gần nhất
    cut = text[:max_len]
    last_stop = max(cut.rfind("."), cut.rfind("!"), cut.rfind("?"), cut.rfind("\n"))
    if last_stop > max_len * 0.6:
        return cut[:last_stop + 1]
    return cut.rsplit(" ", 1)[0] + "…"


def _format_post(post: Dict) -> str:
    """
    Tạo tin nhắn gọn, đẹp:

    🐦 @username · 14:30 02/05
    🔗 https://x.com/...
    ───────────────────
    Nội dung chính tiếng Việt
    """
    username = post["username"]
    orig     = post["text"]
    url      = post["url"]
    date     = post["date"]

    # 1. Lọc rác khỏi text gốc
    clean = _clean_text(orig)

    # 2. Dịch sang tiếng Việt
    translated = _translate(clean)

    # 3. Lấy nội dung chính ngắn gọn
    body = _summarize(translated)

    if not body:
        body = _summarize(_translate(orig))  # fallback nếu clean quá ngắn

    msg = (
        f"🐦 <b>@{username}</b>  ·  <i>{date}</i>\n"
        f"🔗 <a href='{url}'>{url}</a>\n"
        f"───────────────────\n"
        f"{body}"
    )
    return msg


async def send_post(bot: Bot, post: Dict):
    """Gửi một bài viết đến tất cả chat IDs."""
    msg = _format_post(post)
    for chat_id in config.CHAT_IDS:
        try:
            if post.get("has_media") and post.get("media_url"):
                try:
                    await bot.send_photo(
                        chat_id=chat_id,
                        photo=post["media_url"],
                        caption=msg[:1024],
                        parse_mode=ParseMode.HTML,
                    )
                    continue
                except TelegramError:
                    pass

            await bot.send_message(
                chat_id=chat_id,
                text=msg,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=False,
            )
        except TelegramError as e:
            logger.error(f"Loi gui @{post['username']} -> {chat_id}: {e}")


async def send_posts_batch(bot: Bot, posts: List[Dict]):
    """Gửi nhiều bài, delay 2 giây giữa mỗi bài."""
    for i, post in enumerate(posts):
        await send_post(bot, post)
        if i < len(posts) - 1:
            await asyncio.sleep(2)


async def send_notify(bot: Bot, text: str):
    """Gửi thông báo hệ thống."""
    for chat_id in config.CHAT_IDS:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=ParseMode.HTML,
            )
        except TelegramError as e:
            logger.error(f"Loi notify -> {chat_id}: {e}")
