"""
fetcher.py – Lấy bài viết mới từ X (Twitter)
Sử dụng twikit để scrape trực tiếp, thay cho Nitter RSS (đã chết).
"""
import re
import html
import json
import os
import logging
import asyncio
from typing import List, Dict, Optional, Set
from datetime import datetime, timezone, timedelta

import config

logger = logging.getLogger(__name__)

# ── Twikit Client ─────────────────────────────────────────────────────────────

_client = None
_cookies_file = os.path.join(os.path.dirname(__file__), "data", "cookies.json")


async def _get_client():
    """Khởi tạo và đăng nhập twikit client (dùng cookies nếu có)."""
    global _client
    if _client is not None:
        return _client

    from twikit import Client

    client = Client("en-US")

    # Thử dùng cookies đã lưu trước
    if os.path.exists(_cookies_file):
        try:
            client.load_cookies(_cookies_file)
            logger.info("✅ Đã load cookies từ file.")
            _client = client
            return _client
        except Exception as e:
            logger.warning(f"⚠️ Cookies hết hạn, đăng nhập lại: {e}")

    # Đăng nhập bằng credentials
    x_user = config.X_USERNAME
    x_email = config.X_EMAIL
    x_pass = config.X_PASSWORD

    if not x_user or not x_pass:
        logger.error("❌ Thiếu X_USERNAME / X_PASSWORD trong .env!")
        return None

    try:
        await client.login(
            auth_info_1=x_user,
            auth_info_2=x_email,
            password=x_pass,
        )
        # Lưu cookies để lần sau không cần đăng nhập lại
        os.makedirs(os.path.dirname(_cookies_file), exist_ok=True)
        client.save_cookies(_cookies_file)
        logger.info("✅ Đăng nhập X thành công, đã lưu cookies.")
        _client = client
        return _client
    except Exception as e:
        logger.error(f"❌ Đăng nhập X thất bại: {e}")
        return None


def _clean_text(text: str) -> str:
    """Bỏ HTML tags, decode entities."""
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return text.strip()


async def fetch_new_posts(username: str, seen_ids: Set[str], limit: int = None) -> List[Dict]:
    """
    Lấy danh sách bài viết mới (chưa có trong seen_ids) của một tài khoản.
    Trả về list dict: {id, username, text, url, date, has_media, media_url, pub_date}
    """
    limit = limit or config.POSTS_PER_FEED

    client = await _get_client()
    if client is None:
        logger.error(f"❌ Không có client để lấy bài @{username}")
        return []

    try:
        # Lấy user info
        user = await client.get_user_by_screen_name(username)
        if user is None:
            logger.warning(f"⚠️ Không tìm thấy user @{username}")
            return []

        # Lấy tweets gần nhất
        tweets = await user.get_tweets("Tweets", count=20)

        new_posts = []
        for tweet in tweets:
            tweet_id = str(tweet.id)
            if tweet_id in seen_ids:
                continue

            # Lấy ngày
            pub_date = None
            if hasattr(tweet, "created_at_datetime") and tweet.created_at_datetime:
                pub_date = tweet.created_at_datetime
            elif hasattr(tweet, "created_at") and tweet.created_at:
                try:
                    pub_date = datetime.strptime(
                        tweet.created_at, "%a %b %d %H:%M:%S %z %Y"
                    )
                except Exception:
                    pass

            # Bỏ qua bài đăng TRƯỚC khi bot khởi động (chỉ lấy bài hôm nay)
            if pub_date and config.BOT_START_DATE:
                if pub_date < config.BOT_START_DATE:
                    continue

            # Nội dung
            text = _clean_text(tweet.text or "")

            # Media
            media_url = None
            has_media = False
            if hasattr(tweet, "media") and tweet.media:
                has_media = True
                for m in tweet.media:
                    if hasattr(m, "media_url_https"):
                        media_url = m.media_url_https
                        break
                    elif hasattr(m, "url"):
                        media_url = m.url
                        break

            # URL gốc
            orig_url = f"https://x.com/{username}/status/{tweet_id}"

            date_str = pub_date.strftime("%H:%M · %d/%m/%Y") if pub_date else "—"

            new_posts.append({
                "id":        tweet_id,
                "username":  username,
                "text":      text,
                "url":       orig_url,
                "date":      date_str,
                "has_media": has_media,
                "media_url": media_url,
                "pub_date":  pub_date,
            })

            if len(new_posts) >= limit:
                break

        logger.info(f"✅ @{username}: {len(new_posts)} bài mới (tổng {len(tweets) if tweets else 0} tweets)")

        # Sắp xếp cũ → mới
        new_posts.sort(key=lambda p: p["pub_date"] or datetime.min.replace(tzinfo=timezone.utc))
        return new_posts

    except Exception as e:
        logger.error(f"❌ Lỗi khi lấy bài @{username}: {e}")
        return []


async def fetch_all_accounts(usernames: List[str], seen_ids: Set[str]) -> List[Dict]:
    """Lấy bài mới từ tất cả tài khoản, gộp lại và sắp xếp theo thời gian."""
    all_posts = []
    for username in usernames:
        posts = await fetch_new_posts(username, seen_ids)
        all_posts.extend(posts)
        # Delay nhẹ giữa mỗi account để tránh rate limit
        await asyncio.sleep(2)

    # Sắp xếp tất cả theo thời gian cũ → mới
    all_posts.sort(key=lambda p: p["pub_date"] or datetime.min.replace(tzinfo=timezone.utc))
    return all_posts


# ── Fallback: Nitter RSS (backup nếu twikit fail) ────────────────────────────

def _fetch_rss_sync(username: str, seen_ids: Set[str], limit: int = None) -> List[Dict]:
    """
    Fallback dùng Nitter RSS nếu twikit không hoạt động.
    LƯU Ý: Hầu hết Nitter mirrors đã chết, chỉ để backup.
    """
    import requests
    import feedparser
    from email.utils import parsedate_to_datetime

    limit = limit or config.POSTS_PER_FEED
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; XFeedBot/1.0)",
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    }

    mirrors = [
        "https://nitter.net",
        "https://nitter.poast.org",
        "https://nitter.catsarch.com",
    ]

    for host in mirrors:
        url = f"{host.rstrip('/')}/{username}/rss"
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                feed = feedparser.parse(resp.content)
                if feed.entries:
                    logger.info(f"✅ RSS fallback @{username} từ {host} ({len(feed.entries)} entries)")
                    new_posts = []
                    for entry in feed.entries[:20]:
                        post_id = entry.get("id", entry.get("link", ""))
                        if not post_id or post_id in seen_ids:
                            continue

                        pub_date = None
                        try:
                            if hasattr(entry, "published"):
                                pub_date = parsedate_to_datetime(entry.published)
                        except Exception:
                            pass

                        if pub_date and config.BOT_START_DATE and pub_date < config.BOT_START_DATE:
                            continue

                        raw_content = getattr(entry, "summary", "") or getattr(entry, "description", "")
                        text = _clean_text(raw_content)

                        media_url = None
                        has_media = False
                        img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', raw_content, re.IGNORECASE)
                        if img_match:
                            has_media = True
                            media_url = img_match.group(1)

                        link = entry.get("link", "")
                        orig_url = re.sub(r"https?://[^/]+/", "https://x.com/", link)
                        date_str = pub_date.strftime("%H:%M · %d/%m/%Y") if pub_date else "—"

                        new_posts.append({
                            "id": post_id, "username": username,
                            "text": text, "url": orig_url, "date": date_str,
                            "has_media": has_media, "media_url": media_url,
                            "pub_date": pub_date,
                        })
                        if len(new_posts) >= limit:
                            break
                    return new_posts
        except Exception as e:
            logger.warning(f"⚠️ RSS {host} lỗi cho @{username}: {e}")
    return []
