"""Bot command and message handlers."""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from src.config.settings import ADMIN_TELEGRAM_ID, EMBEDDINGS_ENABLED
from src.bot import messages as msg
from src.bot.keyboards import channels_keyboard, start_keyboard, search_results_keyboard
from src.utils.helpers import parse_channel_url, parse_post_url

if EMBEDDINGS_ENABLED:
    from src.services.embedder import get_query_embedding

logger = logging.getLogger(__name__)


def _is_admin(user_id: int) -> bool:
    return user_id == ADMIN_TELEGRAM_ID


def _get_queries(context: ContextTypes.DEFAULT_TYPE):
    return context.bot_data["queries"]


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_admin = _is_admin(update.effective_user.id)
    queries = _get_queries(context)
    has_channels = len(queries.get_active_channels()) > 0
    welcome = msg.WELCOME_ADMIN if is_admin else msg.WELCOME_USER
    await update.message.reply_text(
        welcome, parse_mode="HTML",
        reply_markup=start_keyboard(has_channels, is_admin),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = msg.HELP_ADMIN if _is_admin(update.effective_user.id) else msg.HELP_USER
    await update.message.reply_text(help_text, parse_mode="HTML")


async def channels_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    queries = _get_queries(context)
    channels = queries.get_active_channels()
    if not channels:
        await update.message.reply_text(msg.NO_CHANNELS)
        return
    await update.message.reply_text(
        msg.CHANNELS_HEADER, parse_mode="HTML",
        reply_markup=channels_keyboard(channels),
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    queries = _get_queries(context)
    stats = queries.get_stats()
    await update.message.reply_text(
        msg.STATS_TEMPLATE.format(**stats), parse_mode="HTML"
    )


async def _get_query_embedding(query: str) -> list[float] | None:
    if not EMBEDDINGS_ENABLED:
        return None
    return await get_query_embedding(query)


def _format_search_results(posts: list, channel_username: str = None) -> list[str]:
    """Format search results with inline links."""
    import html as html_lib
    lines = []
    if channel_username:
        lines.append(f"\n📢 @{channel_username}:")
    for p in posts:
        desc = html_lib.escape(p.description or p.text[:60])
        lines.append(f'• <a href="{p.post_url}">{desc}</a>')
    return lines


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        context.user_data["search_global"] = True
        await update.message.reply_text(msg.SEARCH_PROMPT_GLOBAL, parse_mode="HTML")
        return

    query = " ".join(context.args)
    await _do_global_search(update, context, query)


async def _do_global_search(update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
    """Global search across all channels."""
    queries = _get_queries(context)
    channels = queries.get_active_channels()
    query_emb = await _get_query_embedding(query)

    results_lines = []
    for ch in channels:
        if hasattr(queries, "hybrid_search"):
            posts = queries.hybrid_search(ch.id, query, query_emb, limit=10)
        else:
            posts = queries.search_posts(ch.id, query, limit=10)
        if posts:
            results_lines.extend(_format_search_results(posts, ch.username))

    if not results_lines:
        await update.message.reply_text(
            msg.SEARCH_NO_RESULTS.format(query=query),
            reply_markup=search_results_keyboard(),
        )
        return

    text = f"🔍 Результаты по «{query}»:" + "\n".join(results_lines)
    if len(text) > 4000:
        text = text[:4000] + "\n..."
    await update.message.reply_text(
        text, parse_mode="HTML", disable_web_page_preview=True,
        reply_markup=search_results_keyboard(),
    )


async def _do_channel_search(
    update: Update, context: ContextTypes.DEFAULT_TYPE,
    channel_id: int, query: str,
):
    """Search within a specific channel."""
    queries = _get_queries(context)
    query_emb = await _get_query_embedding(query)

    if hasattr(queries, "hybrid_search"):
        posts = queries.hybrid_search(channel_id, query, query_emb, limit=10)
    else:
        posts = queries.search_posts(channel_id, query, limit=10)

    if not posts:
        await update.message.reply_text(
            msg.SEARCH_NO_RESULTS.format(query=query),
            reply_markup=search_results_keyboard(channel_id),
        )
        return

    channel = queries.get_channel_by_id(channel_id)
    lines = _format_search_results(posts, channel.username)
    text = f"🔍 Результаты по «{query}»:" + "\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "\n..."
    await update.message.reply_text(
        text, parse_mode="HTML", disable_web_page_preview=True,
        reply_markup=search_results_keyboard(channel_id),
    )


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle plain text messages — channel URLs, post URLs, search."""
    text = update.message.text.strip()
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

    # Check if it's a post URL (for pinned post setup — admin only)
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
            await update.message.reply_text(
                msg.PINNED_SET.format(message_id=message_id, username=username)
            )
        except Exception as e:
            logger.error("Failed to get chat for @%s: %s", username, e)
            await update.message.reply_text(msg.PINNED_ACCESS_ERROR)
        return

    # Check if it's a channel URL
    username = parse_channel_url(text)
    if username:
        existing = queries.get_channel_by_username(username)
        if existing:
            await update.message.reply_text(msg.CHANNEL_EXISTS.format(username=username))
            return

        is_admin = _is_admin(update.effective_user.id)
        if is_admin:
            queries.add_channel(username, update.effective_user.id)
            await update.message.reply_text(
                msg.CHANNEL_ADDED.format(username=username),
                reply_markup=start_keyboard(True, True),
            )
        else:
            user = update.effective_user
            user_name = user.full_name or user.username or str(user.id)
            await update.message.reply_text(
                msg.CHANNEL_SUGGESTED.format(username=username),
                reply_markup=start_keyboard(True, False),
            )
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_TELEGRAM_ID,
                    text=msg.CHANNEL_SUGGESTION_NOTIFY.format(
                        user_name=user_name, user_id=user.id, username=username,
                    ),
                    parse_mode="HTML",
                )
            except Exception:
                pass
        return

    # Not recognized
    await update.message.reply_text(msg.INVALID_LINK)
