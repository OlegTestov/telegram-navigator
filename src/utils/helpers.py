"""Utility functions."""

import hashlib
import re
import unicodedata


def slugify(text: str) -> str:
    """Convert text to URL-safe slug."""
    text = text.lower().strip()
    text = unicodedata.normalize("NFKD", text)
    # Transliterate basic Cyrillic
    translit = {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "yo",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "й": "y",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "kh",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "shch",
        "ъ": "",
        "ы": "y",
        "ь": "",
        "э": "e",
        "ю": "yu",
        "я": "ya",
    }
    result = []
    for char in text:
        result.append(translit.get(char, char))
    text = "".join(result)
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:40]


def content_hash(text: str) -> str:
    """MD5 hash of text for change detection."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def parse_channel_url(url: str) -> str | None:
    """Extract channel username from Telegram URL or @username.

    Returns username without @ or None if invalid.
    """
    url = url.strip()
    # Handle @username
    if url.startswith("@"):
        return url[1:]
    # Handle t.me/username or https://t.me/username
    match = re.match(r"(?:https?://)?t\.me/([a-zA-Z_]\w{3,})", url)
    if match:
        return match.group(1)
    return None


def parse_post_url(url: str) -> tuple[str, int] | None:
    """Extract (channel_username, message_id) from post URL.

    Returns None if invalid.
    """
    url = url.strip()
    match = re.match(r"(?:https?://)?t\.me/([a-zA-Z_]\w{3,})/(\d+)", url)
    if match:
        return match.group(1), int(match.group(2))
    return None


def truncate(text: str, max_length: int) -> str:
    """Truncate text to max_length, adding ... if needed."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 1] + "…"
