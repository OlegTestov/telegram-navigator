"""Bot command and message handlers."""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from src.config.settings import ADMIN_TELEGRAM_ID
from src.bot import messages as msg
from src.bot.keyboards import channels_keyboard
from src.utils.helpers import parse_channel_url, parse_post_url

logger = logging.getLogger(__name__)


def _is_admin(user_id: int) -> bool:
    return user_id == ADMIN_TELEGRAM_ID


def _get_queries(context: ContextTypes.DEFAULT_TYPE):
    return context.bot_data["queries"]


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text(msg.NOT_ADMIN)
        return
    await update.message.reply_text(msg.WELCOME)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text(msg.NOT_ADMIN)
        return
    await update.message.reply_text(msg.HELP, parse_mode="HTML")


async def channels_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text(msg.NOT_ADMIN)
        return

    queries = _get_queries(context)
    channels = queries.get_active_channels()
    if not channels:
        await update.message.reply_text(msg.NO_CHANNELS)
        return
    await update.message.reply_text(
        "📢 Ваши каналы:", reply_markup=channels_keyboard(channels)
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text(msg.NOT_ADMIN)
        return

    queries = _get_queries(context)
    stats = queries.get_stats()
    await update.message.reply_text(
        msg.STATS_TEMPLATE.format(**stats), parse_mode="HTML"
    )


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text(msg.NOT_ADMIN)
        return

    if not context.args:
        await update.message.reply_text(msg.SEARCH_PROMPT)
        return

    query = " ".join(context.args)
    queries = _get_queries(context)
    channels = queries.get_active_channels()

    results_text = []
    for ch in channels:
        posts = queries.search_posts(ch.id, query, limit=10)
        if posts:
            results_text.append(f"\n📢 @{ch.username}:")
            for p in posts:
                desc = p.description or p.text[:60]
                results_text.append(f"• {desc}\n  {p.post_url}")

    if not results_text:
        await update.message.reply_text(msg.SEARCH_NO_RESULTS.format(query=query))
        return

    text = f"🔍 Результаты по «{query}»:" + "\n".join(results_text)
    # Truncate if too long
    if len(text) > 4000:
        text = text[:4000] + "\n..."
    await update.message.reply_text(text)


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle plain text messages — channel URLs or post URLs."""
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text(msg.NOT_ADMIN)
        return

    text = update.message.text.strip()
    queries = _get_queries(context)

    # Check if it's a post URL (for pinned post setup)
    post_info = parse_post_url(text)
    if post_info:
        username, message_id = post_info
        channel = queries.get_channel_by_username(username)
        if not channel:
            await update.message.reply_text(msg.PINNED_WRONG_CHANNEL)
            return
        # Resolve chat_id from username via bot
        try:
            chat = await context.bot.get_chat(f"@{username}")
            queries.set_channel_pinned(channel.id, chat.id, message_id)
            await update.message.reply_text(
                msg.PINNED_SET.format(message_id=message_id, username=username)
            )
        except Exception as e:
            logger.error("Failed to get chat for @%s: %s", username, e)
            await update.message.reply_text(
                "❌ Не удалось получить доступ к каналу. Убедитесь, что бот добавлен админом."
            )
        return

    # Check if it's a channel URL
    username = parse_channel_url(text)
    if username:
        existing = queries.get_channel_by_username(username)
        if existing:
            await update.message.reply_text(msg.CHANNEL_EXISTS.format(username=username))
            return
        channel = queries.add_channel(username, update.effective_user.id)
        await update.message.reply_text(msg.CHANNEL_ADDED.format(username=username))
        return

    # Not recognized
    await update.message.reply_text(msg.INVALID_LINK)
