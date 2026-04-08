"""Localized UI strings. Use get_messages(lang) to get the right module."""

from src.bot.messages import en, ru

_LANGS = {"ru": ru, "en": en}


def get_messages(lang: str = "ru"):
    """Return language module. Falls back to Russian."""
    return _LANGS.get(lang, ru)
