"""Application settings and configuration."""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, LOG_LEVEL),
)

# Telethon
TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "")
TELEGRAM_SESSION_STRING = os.getenv("TELEGRAM_SESSION_STRING", "")

# Bot
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")

# Database
DB_BACKEND = os.getenv("DB_BACKEND", "sqlite")  # "sqlite" or "supabase"
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "data/content_table.db")

# Supabase (only needed if DB_BACKEND=supabase)
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

# OpenAI (embeddings)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_BATCH_SIZE = int(os.getenv("EMBEDDING_BATCH_SIZE", "100"))
EMBEDDINGS_ENABLED = bool(OPENAI_API_KEY)

# Admin
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))

# Pipeline
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "50"))

# Content language defaults (can be overridden via bot admin settings in DB)
CONTENT_LANGUAGE = os.getenv("CONTENT_LANGUAGE", "en")
TRANSLATION_LANGUAGES = os.getenv("TRANSLATION_LANGUAGES", "ru")
DIGEST_INTERVAL_HOURS_DEFAULT = os.getenv("DIGEST_INTERVAL_HOURS", "3")

# Settings defaults for first run (before admin configures via bot)
_SETTING_DEFAULTS = {
    "content_language": CONTENT_LANGUAGE,
    "translation_languages": TRANSLATION_LANGUAGES,
    "digest_interval_hours": DIGEST_INTERVAL_HOURS_DEFAULT,
}


def get_setting(queries, key: str) -> str:
    """Read setting: DB → .env → hardcoded default."""
    val = queries.get_bot_setting(key)
    if val is not None:
        return val
    return _SETTING_DEFAULTS.get(key, "")


def get_translation_languages(queries) -> list[str]:
    """Parse translation_languages setting into a list."""
    raw = get_setting(queries, "translation_languages")
    return [lang.strip() for lang in raw.split(",") if lang.strip()]


def validate_config() -> bool:
    required = {
        "TELEGRAM_API_ID": TELEGRAM_API_ID,
        "TELEGRAM_API_HASH": TELEGRAM_API_HASH,
        "TELEGRAM_SESSION_STRING": TELEGRAM_SESSION_STRING,
        "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
        "GEMINI_API_KEY": GEMINI_API_KEY,
        "ADMIN_TELEGRAM_ID": ADMIN_TELEGRAM_ID,
    }
    if DB_BACKEND == "supabase":
        required["SUPABASE_URL"] = SUPABASE_URL
        required["SUPABASE_KEY"] = SUPABASE_KEY
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    return True
