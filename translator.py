"""
translator.py – Dịch bài viết sang tiếng Việt + tóm tắt đơn giản
"""
import re
import logging
from deep_translator import GoogleTranslator

logger = logging.getLogger(__name__)


def _is_mostly_english(text: str) -> bool:
    """Kiểm tra xem text có chủ yếu là tiếng Anh không."""
    # Nếu text đã có nhiều ký tự tiếng Việt thì không cần dịch
    viet_chars = set("àáảãạăắặẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ")
    count_viet = sum(1 for c in text.lower() if c in viet_chars)
    if count_viet > 5:
        return False
    return True


def translate_to_vietnamese(text: str) -> str:
    """Dịch text sang tiếng Việt. Trả về text gốc nếu lỗi."""
    if not text or not text.strip():
        return text

    # Không dịch nếu đã là tiếng Việt
    if not _is_mostly_english(text):
        return text

    # Giới hạn độ dài (Google Translate free có giới hạn 5000 ký tự)
    text_to_translate = text[:4000]

    try:
        translated = GoogleTranslator(source="auto", target="vi").translate(text_to_translate)
        return translated if translated else text
    except Exception as e:
        logger.warning(f"⚠️ Không dịch được: {e}")
        return text  # Trả về bản gốc nếu lỗi


def detect_investment_keywords(text: str) -> str:
    """
    Phát hiện từ khóa liên quan đến đầu tư và trả về nhận định ngắn.
    Phù hợp cho học sinh mới tìm hiểu.
    """
    text_lower = text.lower()

    # Crypto / Chứng khoán
    if any(k in text_lower for k in ["bitcoin", "btc", "crypto", "ethereum", "eth", "altcoin", "nft"]):
        return "🪙 Liên quan đến crypto/tiền số"
    if any(k in text_lower for k in ["stock", "market", "nasdaq", "s&p", "dow", "invest", "portfolio"]):
        return "📈 Liên quan đến chứng khoán/thị trường"
    if any(k in text_lower for k in ["ai", "artificial intelligence", "chatgpt", "llm", "openai", "gemini"]):
        return "🤖 Liên quan đến AI/công nghệ"
    if any(k in text_lower for k in ["startup", "funding", "ipo", "venture", "billion", "million"]):
        return "💼 Liên quan đến kinh doanh/khởi nghiệp"
    if any(k in text_lower for k in ["war", "china", "tariff", "sanction", "economy", "gdp", "inflation"]):
        return "🌍 Liên quan đến kinh tế/địa chính trị"
    if any(k in text_lower for k in ["elon", "trump", "fed", "interest rate", "rate cut"]):
        return "🏛️ Liên quan đến chính sách/nhân vật quan trọng"

    return ""  # Không phát hiện từ khóa đặc biệt


def summarize_for_student(original_text: str, translated_text: str) -> str:
    """
    Tạo tóm tắt ngắn gọn (1-2 câu) phù hợp cho học sinh.
    Dùng bản dịch nếu có, không thì dùng bản gốc.
    """
    text = translated_text if translated_text else original_text

    # Lấy câu đầu tiên (thường là ý chính)
    sentences = re.split(r'[.!?\n]', text)
    first = next((s.strip() for s in sentences if len(s.strip()) > 20), "")

    if len(text) <= 150:
        return text  # Ngắn rồi, không cần tóm tắt

    if first and len(first) < 200:
        return first

    return text[:150].rsplit(" ", 1)[0] + "…"
