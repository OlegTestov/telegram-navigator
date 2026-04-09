"""Per-user language detection, caching, and translation helpers."""

from telegram import Update
from telegram.ext import ContextTypes


def apply_translations(entities, translations: dict, fields: list[str]):
    """Apply translations dict to entity list in-place.

    Args:
        entities: List of dataclass instances with .id attribute.
        translations: {entity_id: {"field": "value", ...}} from get_*_translations().
        fields: List of field names to override (e.g., ["name", "summary"]).

    Returns the same entities list (modified in-place).
    """
    for entity in entities:
        tr = translations.get(entity.id)
        if tr:
            for field in fields:
                val = tr.get(field) if isinstance(tr, dict) else tr
                if val:
                    setattr(entity, field, val)
    return entities


def apply_post_translations(posts, translations: dict):
    """Apply post description translations. translations: {post_id: description}."""
    for post in posts:
        if post.id in translations:
            post.description = translations[post.id]
    return posts


def get_user_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
    """Get user's language: cache -> DB -> Telegram auto-detect -> 'ru'.

    Sync function -- DB lookup is a single-row primary key query, fast enough
    for the event loop (same pattern as all other query methods in the project).
    """
    if "lang" in context.user_data:
        return context.user_data["lang"]

    queries = context.bot_data["queries"]
    user_id = update.effective_user.id

    # Check DB
    lang = queries.get_user_language(user_id)
    if lang:
        context.user_data["lang"] = lang
        return lang

    # Auto-detect from Telegram language_code
    tg_lang = (update.effective_user.language_code or "").lower()
    lang = "ru" if tg_lang.startswith(("ru", "uk", "be")) else "en"

    # Persist to DB
    queries.set_user_language(user_id, lang)
    context.user_data["lang"] = lang
    return lang
