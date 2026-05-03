"""
config.py – Cấu hình XFeed Bot
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Telegram ──────────────────────────────────────────────
BOT_TOKEN      = os.getenv("TELEGRAM_BOT_TOKEN", "")
# Hỗ trợ nhiều chat ID, phân cách bằng dấu phẩy
_raw_ids       = os.getenv("TELEGRAM_CHAT_ID", "")
CHAT_IDS       = [c.strip() for c in _raw_ids.split(",") if c.strip()]
CHAT_ID        = CHAT_IDS[0] if CHAT_IDS else ""  # Giữ backward compat

# ── X (Twitter) Credentials ──────────────────────────────
# Cần để dùng twikit scraper (Nitter đã chết)
X_USERNAME     = os.getenv("X_USERNAME", "")
X_EMAIL        = os.getenv("X_EMAIL", "")
X_PASSWORD     = os.getenv("X_PASSWORD", "")

# ── Scheduler ─────────────────────────────────────────────
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL_MINUTES", "240"))

# ── Storage ───────────────────────────────────────────────
DATA_DIR       = os.path.join(os.path.dirname(__file__), "data")
ACCOUNTS_FILE  = os.path.join(DATA_DIR, "accounts.json")
SEEN_FILE      = os.path.join(DATA_DIR, "seen_posts.json")

# ── Giới hạn ──────────────────────────────────────────────
MAX_ACCOUNTS   = 50
MAX_SEEN_IDS   = 5000
POSTS_PER_FEED = 10

# Chỉ lấy bài đăng từ HÔM NAY trở đi (00:00 giờ VN)
from datetime import datetime, timezone, timedelta
_vn_tz = timezone(timedelta(hours=7))
BOT_START_DATE = datetime.now(_vn_tz).replace(hour=0, minute=0, second=0, microsecond=0)

# ── Validate ──────────────────────────────────────────────
if not BOT_TOKEN:
    raise ValueError("❌ Thiếu TELEGRAM_BOT_TOKEN trong file .env!")
if not CHAT_IDS:
    raise ValueError("❌ Thiếu TELEGRAM_CHAT_ID trong file .env!")
