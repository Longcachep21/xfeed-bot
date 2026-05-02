"""
storage.py – Lưu/đọc danh sách tài khoản và post đã thấy
"""
import json
import os
from typing import Set, List

import config


# ── Danh sách tài khoản crypto nổi tiếng sẵn có ──────────────────────────────
CRYPTO_PRESETS = {
    "CEO sàn giao dịch": [
        "cz_binance",       # CZ – Binance
        "brian_armstrong",  # Brian Armstrong – Coinbase
        "justinsuntron",    # Justin Sun – HTX / TRON
        "krakenfx",         # Kraken Exchange
        "coinbase",         # Coinbase chính thức
        "binance",          # Binance chính thức
        "okx",              # OKX Exchange
        "Bybit_Official",   # Bybit
        "gate_io",          # Gate.io
    ],
    "Bitcoin & Macro": [
        "saylor",           # Michael Saylor – MicroStrategy
        "APompliano",       # Anthony Pompliano
        "100trillionUSD",   # PlanB – Stock to Flow
        "woonomic",         # Willy Woo – On-chain
        "DocumentingBTC",   # Bitcoin milestones
        "BitcoinMagazine",  # Bitcoin Magazine
        "RaoulGMI",         # Raoul Pal – Macro
    ],
    "Ethereum & DeFi": [
        "VitalikButerin",   # Vitalik Buterin – Ethereum founder
        "ethereum",         # Ethereum chính thức
        "stanikulechov",    # Stani – Aave
        "haydenzadams",     # Hayden Adams – Uniswap
    ],
    "Tin tức & Phân tích": [
        "CoinDesk",         # CoinDesk News
        "Cointelegraph",    # Cointelegraph
        "WatcherGuru",      # Breaking crypto news
        "lookonchain",      # On-chain tracking
        "glassnode",        # On-chain data
        "CryptoQuant_CEO",  # Ki Young Ju – CryptoQuant
    ],
    "Nhân vật ảnh hưởng": [
        "elonmusk",         # Elon Musk
        "naval",            # Naval Ravikant
        "aantonop",         # Andreas Antonopoulos
        "DylanLeClair_",    # Dylan LeClair
    ],
    "KOL Việt Nam": [
        "thanhle_crypto",   # Thanh Lê – Co-founder Coin98 / NinetyEight
        "trungtnguyen",     # Trung Nguyễn – CEO Axie Infinity / Sky Mavis
        "larsenej",         # Aleksander Larsen – Co-founder Axie Infinity
        "zane_kyros",       # Thuat Nguyễn – Founder Kyros Ventures & Ancient8
        "NinetyEight_HQ",   # NinetyEight (Coin98) – Hệ sinh thái DeFi lớn nhất VN
        "coin68tv",         # Coin68 – Trang tin crypto lớn nhất VN
        "blogtienao",       # Blogtienao – Cộng đồng crypto VN
        "Ancient8_gg",      # Ancient8 – GameFi & Web3 VN
        "KyrosVentures",    # Kyros Ventures – Quỹ đầu tư crypto VN
        "coin98finance",    # Coin98 Finance – Ví & DeFi
    ],
    "Kênh tôi theo dõi": [
        "DonAlt",           # DonAlt – Phân tích kỹ thuật crypto
        "cryptorover",      # Crypto Rover – Tin tức & phân tích
        "drofin69",         # Drofin – Trading crypto
        "mrweb5vn",         # Mr Web5 VN – KOL crypto Việt Nam
        "0xNDTNT",          # 0xNDTNT – Crypto VN
    ],
}


def _ensure_dir():
    os.makedirs(config.DATA_DIR, exist_ok=True)


# ── Accounts ──────────────────────────────────────────────────────────────────

def load_accounts() -> List[str]:
    _ensure_dir()
    if not os.path.exists(config.ACCOUNTS_FILE):
        return []
    try:
        with open(config.ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, IOError):
        return []


def save_accounts(accounts: List[str]):
    _ensure_dir()
    with open(config.ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(accounts, f, ensure_ascii=False, indent=2)


def add_account(username: str) -> bool:
    username = username.lstrip("@").lower().strip()
    accounts = load_accounts()
    if username in accounts:
        return False
    if len(accounts) >= config.MAX_ACCOUNTS:
        return False
    accounts.append(username)
    save_accounts(accounts)
    return True


def remove_account(username: str) -> bool:
    username = username.lstrip("@").lower().strip()
    accounts = load_accounts()
    if username not in accounts:
        return False
    accounts.remove(username)
    save_accounts(accounts)
    return True


def load_preset(category: str = None) -> int:
    """
    Thêm tài khoản từ danh sách preset vào danh sách theo dõi.
    Nếu category=None thì thêm tất cả.
    Trả về số tài khoản đã thêm mới.
    """
    added = 0
    if category and category in CRYPTO_PRESETS:
        usernames = CRYPTO_PRESETS[category]
    else:
        usernames = [u for lst in CRYPTO_PRESETS.values() for u in lst]

    for username in usernames:
        if add_account(username):
            added += 1
    return added


# ── Seen Posts ────────────────────────────────────────────────────────────────

def load_seen() -> Set[str]:
    _ensure_dir()
    if not os.path.exists(config.SEEN_FILE):
        return set()
    try:
        with open(config.SEEN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(data) if isinstance(data, list) else set()
    except (json.JSONDecodeError, IOError):
        return set()


def save_seen(seen: Set[str]):
    _ensure_dir()
    seen_list = list(seen)[-config.MAX_SEEN_IDS:]
    with open(config.SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(seen_list, f)


def mark_seen(post_ids: List[str]):
    seen = load_seen()
    seen.update(post_ids)
    save_seen(seen)
