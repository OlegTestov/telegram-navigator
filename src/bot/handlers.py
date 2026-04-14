"""Bot command and message handlers."""

import html as html_lib
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.bot.keyboards import channels_keyboard, search_results_keyboard, start_keyboard
from src.bot.messages import get_messages
from src.config.settings import ADMIN_TELEGRAM_ID, EMBEDDINGS_ENABLED, get_setting
from src.utils.helpers import parse_channel_url, parse_post_url
from src.utils.i18n import apply_post_translations, get_user_lang

if EMBEDDINGS_ENABLED:
    from src.services.embedder import get_query_embedding

logger = logging.getLogger(__name__)


def _is_admin(user_id: int) -> bool:
    return user_id == ADMIN_TELEGRAM_ID


def _get_queries(context: ContextTypes.DEFAULT_TYPE):
    return context.bot_data["queries"]


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_user_lang(update, context)
    msg = get_messages(lang)
    is_admin = _is_admin(update.effective_user.id)
    queries = _get_queries(context)
    has_channels = len(queries.get_active_channels()) > 0
    welcome = msg.WELCOME_ADMIN if is_admin else msg.WELCOME_USER
    await update.message.reply_text(
        welcome,
        parse_mode="HTML",
        reply_markup=start_keyboard(has_channels, is_admin, lang=lang),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_user_lang(update, context)
    msg = get_messages(lang)
    help_text = msg.HELP_ADMIN if _is_admin(update.effective_user.id) else msg.HELP_USER
    await update.message.reply_text(help_text, parse_mode="HTML")


async def channels_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_user_lang(update, context)
    msg = get_messages(lang)
    queries = _get_queries(context)
    channels = queries.get_active_channels()
    if not channels:
        await update.message.reply_text(msg.NO_CHANNELS)
        return
    await update.message.reply_text(
        msg.CHANNELS_HEADER,
        parse_mode="HTML",
        reply_markup=channels_keyboard(channels, lang=lang),
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_user_lang(update, context)
    msg = get_messages(lang)
    queries = _get_queries(context)
    stats = queries.get_stats()
    await update.message.reply_text(msg.STATS_TEMPLATE.format(**stats), parse_mode="HTML")


async def _get_query_embedding(query: str) -> list[float] | None:
    if not EMBEDDINGS_ENABLED:
        return None
    return await get_query_embedding(query)


def _format_search_results(posts: list, channel_username: str = None) -> list[str]:
    """Format search results with inline links."""
    lines = []
    if channel_username:
        lines.append(f"\n\U0001f4e2 @{channel_username}:")
    for p in posts:
        desc = html_lib.escape(p.description or p.text[:60])
        lines.append(f'• <a href="{p.post_url}">{desc}</a>')
    return lines


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_user_lang(update, context)
    msg = get_messages(lang)
    if not context.args:
        context.user_data["search_global"] = True
        await update.message.reply_text(msg.SEARCH_PROMPT_GLOBAL, parse_mode="HTML")
        return

    query = " ".join(context.args)
    await _do_global_search(update, context, query)


async def _do_global_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    """Global search across all channels."""
    lang = get_user_lang(update, context)
    msg = get_messages(lang)
    queries = _get_queries(context)
    channels = queries.get_active_channels()
    query_emb = await _get_query_embedding(query)

    content_lang = get_setting(queries, "content_language")
    results_lines = []
    for ch in channels:
        if hasattr(queries, "hybrid_search"):
            posts = queries.hybrid_search(ch.id, query, query_emb, limit=7)
        else:
            posts = queries.search_posts(ch.id, query, limit=7)
        if posts:
            if lang != content_lang:
                post_tr = queries.get_post_translations([p.id for p in posts], lang)
                apply_post_translations(posts, post_tr)
            results_lines.extend(_format_search_results(posts, ch.username))

    if not results_lines:
        await update.message.reply_text(
            msg.SEARCH_NO_RESULTS.format(query=query),
            reply_markup=search_results_keyboard(lang=lang),
        )
        return

    header = msg.SEARCH_RESULTS_HEADER.format(query=html_lib.escape(query))
    # Build text line by line to avoid cutting HTML tags
    text = header
    for line in results_lines:
        if len(text) + len(line) + 1 > 4000:
            text += "\n..."
            break
        text += "\n" + line
    await update.message.reply_text(
        text,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=search_results_keyboard(lang=lang),
    )


async def _do_channel_search(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    channel_id: int,
    query: str,
):
    """Search within a specific channel."""
    lang = get_user_lang(update, context)
    msg = get_messages(lang)
    queries = _get_queries(context)
    query_emb = await _get_query_embedding(query)

    if hasattr(queries, "hybrid_search"):
        posts = queries.hybrid_search(channel_id, query, query_emb, limit=7)
    else:
        posts = queries.search_posts(channel_id, query, limit=7)

    if not posts:
        await update.message.reply_text(
            msg.SEARCH_NO_RESULTS.format(query=query),
            reply_markup=search_results_keyboard(channel_id, lang=lang),
        )
        return

    content_lang = get_setting(queries, "content_language")
    if lang != content_lang:
        post_tr = queries.get_post_translations([p.id for p in posts], lang)
        apply_post_translations(posts, post_tr)

    channel = queries.get_channel_by_id(channel_id)
    lines = _format_search_results(posts, channel.username)
    header = msg.SEARCH_RESULTS_HEADER.format(query=html_lib.escape(query))
    text = header
    for line in lines:
        if len(text) + len(line) + 1 > 4000:
            text += "\n..."
            break
        text += "\n" + line
    await update.message.reply_text(
        text,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=search_results_keyboard(channel_id, lang=lang),
    )


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle plain text messages -- channel URLs, post URLs, search."""
    text = update.message.text.strip()
    lang = get_user_lang(update, context)
    msg = get_messages(lang)
    queries = _get_queries(context)

    # Global search (from start menu button)
    if context.user_data.pop("search_global", None):
        await _do_global_search(update, context, text)
        return

    # Per-channel search (from inline button)
    search_channel_id = context.user_data.pop("search_channel_id", None)
    if search_channel_id:
        await _do_channel_search(update, context, search_channel_id, text)
        return

    # Check if it's a post URL (for pinned post setup -- admin only)
    post_info = parse_post_url(text)
    if post_info:
        if not _is_admin(update.effective_user.id):
            await update.message.reply_text(msg.NOT_ADMIN)
            return
        username, message_id = post_info
        channel = queries.get_channel_by_username(username)
        if not channel:
            await update.message.reply_text(msg.PINNED_WRONG_CHANNEL)
            return
        try:
            chat = await context.bot.get_chat(f"@{username}")
            queries.set_channel_pinned(channel.id, chat.id, message_id)
            await update.message.reply_text(msg.PINNED_SET.format(message_id=message_id, username=username))
        except Exception as e:
            logger.error("Failed to get chat for @%s: %s", username, e)
            await update.message.reply_text(msg.PINNED_ACCESS_ERROR)
        return

    # Check if it's a channel URL
    username = parse_channel_url(text)
    if username:
        existing = queries.get_channel_by_username(username)
        if existing:
            menu_kb = InlineKeyboardMarkup([[InlineKeyboardButton(msg.KB_OPEN_MENU, callback_data="open_menu")]])
            await update.message.reply_text(msg.CHANNEL_EXISTS.format(username=username), reply_markup=menu_kb)
            return

        is_admin = _is_admin(update.effective_user.id)
        if is_admin:
            queries.add_channel(username, update.effective_user.id)
            await update.message.reply_text(
                msg.CHANNEL_ADDED.format(username=username),
                reply_markup=start_keyboard(True, True, lang=lang),
            )
        else:
            user = update.effective_user
            user_name = user.full_name or user.username or str(user.id)
            await update.message.reply_text(
                msg.CHANNEL_SUGGESTED.format(username=username),
                reply_markup=start_keyboard(True, False, lang=lang),
            )
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_TELEGRAM_ID,
                    text=msg.CHANNEL_SUGGESTION_NOTIFY.format(
                        user_name=user_name,
                        user_id=user.id,
                        username=username,
                    ),
                    parse_mode="HTML",
                )
            except Exception:
                pass
        return

    # Not recognized
    await update.message.reply_text(msg.INVALID_LINK)
