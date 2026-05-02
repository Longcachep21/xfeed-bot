"""
fetcher.py – Lấy bài viết mới từ Nitter RSS
"""
import re
import html
import logging
import requests
import feedparser
from typing import List, Dict, Optional
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import config

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; XFeedBot/1.0; +https://github.com/xfeedbot)",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}


def _rss_url(username: str, host: str) -> str:
    return f"{host.rstrip('/')}/{username}/rss"


def _clean_html(raw: str) -> str:
    """Xóa HTML tags, decode entities."""
    text = re.sub(r"<br\s*/?>", "\n", raw, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return text.strip()


def _parse_date(entry) -> Optional[datetime]:
    """Lấy ngày giờ từ entry RSS."""
    try:
        if hasattr(entry, "published"):
            return parsedate_to_datetime(entry.published)
        if hasattr(entry, "updated"):
            return parsedate_to_datetime(entry.updated)
    except Exception:
        pass
    return None


def _fetch_rss(username: str) -> Optional[feedparser.FeedParserDict]:
    """Thử lấy RSS từ các mirror, trả về feed nếu thành công."""
    mirrors = [config.NITTER_HOST] + [
        m for m in config.NITTER_MIRRORS if m != config.NITTER_HOST
    ]
    for host in mirrors:
        url = _rss_url(username, host)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            if resp.status_code == 200:
                feed = feedparser.parse(resp.content)
                if feed.entries:
                    logger.info(f"✅ Lấy RSS @{username} từ {host} ({len(feed.entries)} entries)")
                    return feed
        except requests.RequestException as e:
            logger.warning(f"⚠️ {host} lỗi cho @{username}: {e}")
    logger.error(f"❌ Không thể lấy RSS @{username} từ bất kỳ server nào")
    return None


def fetch_new_posts(username: str, seen_ids: set, limit: int = None) -> List[Dict]:
    """
    Lấy danh sách bài viết mới (chưa có trong seen_ids) của một tài khoản.
    Trả về list dict: {id, username, text, url, date, has_media, media_url}
    """
    limit = limit or config.POSTS_PER_FEED
    feed = _fetch_rss(username)
    if not feed:
        return []

    new_posts = []
    for entry in feed.entries[:20]:  # Kiểm tra tối đa 20 entries gần nhất
        post_id = entry.get("id", entry.get("link", ""))
        if not post_id or post_id in seen_ids:
            continue

        # Lấy ngày sớm để lọc bài cũ
        pub_date = _parse_date(entry)

        # Bỏ qua bài đăng TRƯỚC khi bot khởi động
        if pub_date and config.BOT_START_DATE and pub_date < config.BOT_START_DATE:
            continue

        # Lấy nội dung
        raw_content = ""
        if hasattr(entry, "summary"):
            raw_content = entry.summary
        elif hasattr(entry, "description"):
            raw_content = entry.description

        text = _clean_html(raw_content)

        # Phát hiện ảnh/video trong entry
        media_url = None
        has_media = False
        img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', raw_content, re.IGNORECASE)
        if img_match:
            has_media = True
            media_url = img_match.group(1)

        # URL gốc (chuyển từ nitter về twitter/x.com)
        link = entry.get("link", "")
        orig_url = re.sub(r"https?://[^/]+/", "https://x.com/", link)

        date_str = pub_date.strftime("%H:%M · %d/%m/%Y") if pub_date else "—"

        new_posts.append({
            "id":        post_id,
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

    # Sắp xếp cũ → mới để gửi theo thứ tự
    new_posts.sort(key=lambda p: p["pub_date"] or datetime.min.replace(tzinfo=timezone.utc))
    return new_posts


def fetch_all_accounts(usernames: List[str], seen_ids: set) -> List[Dict]:
    """Lấy bài mới từ tất cả tài khoản, gộp lại và sắp xếp theo thời gian."""
    all_posts = []
    for username in usernames:
        posts = fetch_new_posts(username, seen_ids)
        all_posts.extend(posts)

    # Sắp xếp tất cả theo thời gian cũ → mới
    all_posts.sort(key=lambda p: p["pub_date"] or datetime.min.replace(tzinfo=timezone.utc))
    return all_posts
