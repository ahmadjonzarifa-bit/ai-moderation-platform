import re
from typing import Tuple, Optional

# 1. Ссылки и домены (включая кириллические домены)
URL_PATTERN = re.compile(
    r"(?:https?:\/\/|ftp:\/\/|tg:\/\/|www\.)[^\s/$.?#].[^\s]*|"
    r"\b[a-zA-Zа-яА-Я0-9-]+\.(?:com|ru|uz|org|net|info|io|me|biz|su|рф|co|app|xyz|dev|site|online|tech)\b|"
    r"\b(?:t\.me|telegram\.me|bit\.ly|tinyurl\.com|goo\.gl|wa\.me|clck\.ru)\b|"
    r"\bt\s*\.\s*m\s*e\s*/|"
    r"(?:точка\s*ком|dot\s*com|точка\s*ру|точка\s*уз)\b|"
    r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
    re.IGNORECASE | re.UNICODE
)

# 2. Email
EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"
)

# 3. Юзернеймы мессенджеров (@username), исключая системные теги платформы (@system, @admin, @bot)
USERNAME_PATTERN = re.compile(
    r"(?<!\w)@(?!system\b)(?!admin\b)(?!bot\b)[a-zA-Z0-9_]{3,32}\b",
    re.IGNORECASE
)

# 4. Номера банковских карт: 16 цифр (8600, 9860, 4, 5 и др.), в т.ч. через пробелы/дефисы
BANK_CARD_PATTERN = re.compile(
    r"\b(?:\d{4}[\s-]?){3}\d{4}\b"
)

# 5. Номера телефонов: +998..., +7..., 8..., 998...
PHONE_PATTERN = re.compile(
    r"(?:(?:\+?998|\+?7|8)[\s\-]?)?(?:\(?\d{2,3}\)?[\s\-]?)?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}\b|"
    r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
    re.IGNORECASE
)

# 6. Стоп-слова (Русский, Узбекский кириллица/латиница, Английский)
STOPWORDS_PATTERNS = [
    # Русский мат и грубые оскорбления
    r"\b(?:х[уеёuy][йеяиюeji]|п[иеie]зд[аеыуoyia]|бл[яеyea][дьdt]|еб[аеиоёuyoea]|ёб[а-я]|пид[оаo]р[а-я]*|муд[аоae]к[а-я]*|сук[аиoy]|гандон[а-я]*|презерватив[а-я]*|шлюх[аиoy]|проститутк[аиoy]|тварь)\b",
    r"\b(?:сука|падла|мразь|ублюдок|долбоеб|долбоёб|шлюха|шалава|гандон|хуйло|залупа)\b",
    # Английские
    r"\b(?:fuck|shit|bitch|cunt|asshole|bastard|dick|pussy|fucker|motherfucker|whore|slut)\b",
    # Узбекские (латиница и кириллица)
    r"\b(?:jalab|s[iı]k[a-z]*|qo['`]?toq|itvachcha|haromi|onangni|onangdi|amcha|shilta|iflos)\b",
    r"\b(?:жалаб|сикиш|сикаман|куток|қўтоқ|итвачча|ҳароми|онангни|оненгни|шалава|ифлос)\b"
]

STOPWORDS_COMPILED = [re.compile(p, re.IGNORECASE | re.UNICODE) for p in STOPWORDS_PATTERNS]

def check_text_regex(text: str) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """
    Проверяет текст сообщения по регулярным выражениям.
    Возвращает кортеж:
    (is_valid, error_reason, violation_type, matched_text)
    """
    if not text or not text.strip():
        return False, "Текст сообщения не может быть пустым", "EMPTY", None

    clean_text = text.strip()

    # 1. Проверка на Email (до проверки обычных URL, чтобы email не путался с доменом)
    email_match = EMAIL_PATTERN.search(clean_text)
    if email_match:
        return False, "В сообщении запрещено указывать адреса электронной почты", "EMAIL", email_match.group(0)

    # 2. Проверка на юзернеймы мессенджеров
    username_match = USERNAME_PATTERN.search(clean_text)
    if username_match:
        return False, "В сообщении запрещено указывать контакты мессенджеров и соцсетей (@username)", "USERNAME", username_match.group(0)

    # 3. Проверка на ссылки и домены
    url_match = URL_PATTERN.search(clean_text)
    if url_match:
        return False, "В сообщении обнаружены запрещенные ссылки или упоминания сайтов", "LINKS", url_match.group(0)

    # 4. Проверка на банковские карты
    card_match = BANK_CARD_PATTERN.search(clean_text)
    if card_match:
        return False, "В сообщении обнаружен номер банковской карты или реквизиты", "BANK_CARD", card_match.group(0)

    # 5. Проверка на номера телефонов
    for phone_candidate in PHONE_PATTERN.finditer(clean_text):
        matched_str = phone_candidate.group(0).strip()
        digits = re.sub(r"\D", "", matched_str)
        if len(digits) >= 7:
            return False, "В сообщении запрещено указывать телефонные номера", "PHONE", matched_str

    # 6. Проверка на стоп-слова
    for pattern in STOPWORDS_COMPILED:
        stop_match = pattern.search(clean_text)
        if stop_match:
            return False, "В сообщении запрещено использовать ненормативную лексику или грубые оскорбления", "PROFANITY", stop_match.group(0)

    return True, None, None, None
