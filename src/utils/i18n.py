"""Per-user language detection and caching."""

from telegram import Update
from telegram.ext import ContextTypes


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
