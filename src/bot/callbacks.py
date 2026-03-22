"""Inline keyboard callback handlers."""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from src.config.settings import ADMIN_TELEGRAM_ID
from src.bot import messages as msg
from src.bot.keyboards import (
    channels_keyboard,
    channel_actions_keyboard,
    topics_keyboard,
    posts_keyboard,
    channel_settings_keyboard,
)
from src.services.toc_generator import generate_compact_toc
from src.config.constants import POSTS_PER_PAGE
from src.utils.helpers import truncate

logger = logging.getLogger(__name__)


def _get_queries(context: ContextTypes.DEFAULT_TYPE):
    return context.bot_data["queries"]


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route callback queries."""
    query = update.callback_query
    await query.answer()

    if update.effective_user.id != ADMIN_TELEGRAM_ID:
        await query.edit_message_text(msg.NOT_ADMIN)
        return

    data = query.data
    queries = _get_queries(context)

    if data == "noop":
        return

    if data == "channels":
        channels = queries.get_active_channels()
        if not channels:
            await query.edit_message_text(msg.NO_CHANNELS)
            return
        await query.edit_message_text(
            "📢 Ваши каналы:", reply_markup=channels_keyboard(channels)
        )
        return

    # Channel selected: ch:{channel_id}
    if data.startswith("ch:"):
        channel_id = int(data.split(":")[1])
        channel = queries.get_channel_by_id(channel_id)
        if not channel:
            await query.edit_message_text("❌ Канал не найден.")
            return

        toc = generate_compact_toc(channel, queries)
        await query.edit_message_text(
            toc, reply_markup=channel_actions_keyboard(channel_id)
        )
        return

    # Topics list: topics:{channel_id}:{page}
    if data.startswith("topics:"):
        parts = data.split(":")
        channel_id = int(parts[1])
        page = int(parts[2])
        topics = queries.get_topics(channel_id)
        if not topics:
            await query.edit_message_text("📭 Тем пока нет.")
            return
        await query.edit_message_text(
            "📋 Темы:", reply_markup=topics_keyboard(topics, channel_id, page)
        )
        return

    # Topic selected: topic:{channel_id}:{slug}:{page}
    if data.startswith("topic:"):
        parts = data.split(":")
        channel_id = int(parts[1])
        slug = parts[2]
        page = int(parts[3])

        topic = queries.get_topic_by_slug(channel_id, slug)
        if not topic:
            await query.edit_message_text("❌ Тема не найдена.")
            return

        posts = queries.get_posts_by_topic(topic.id, page=page, limit=POSTS_PER_PAGE)
        total = queries.get_topic_post_count(topic.id)

        # Build message
        emoji = topic.emoji or "📌"
        lines = [f"{emoji} <b>{topic.name}</b> ({total} постов)"]
        if topic.summary:
            lines.append(f"<i>{topic.summary}</i>")
        lines.append("")

        for i, post in enumerate(posts, start=page * POSTS_PER_PAGE + 1):
            desc = post.description or truncate(post.text, 60)
            lines.append(f"{i}. <a href=\"{post.post_url}\">{desc}</a>")

        text = "\n".join(lines)
        if len(text) > 4000:
            text = text[:4000] + "\n..."

        await query.edit_message_text(
            text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=posts_keyboard(posts, channel_id, slug, page, total),
        )
        return

    # Search: search:{channel_id}
    if data.startswith("search:"):
        channel_id = int(data.split(":")[1])
        context.user_data["search_channel_id"] = channel_id
        await query.edit_message_text(
            "🔍 Введите поисковый запрос (или /channels для возврата):"
        )
        return

    # Settings: settings:{channel_id}
    if data.startswith("settings:"):
        channel_id = int(data.split(":")[1])
        channel = queries.get_channel_by_id(channel_id)
        if not channel:
            await query.edit_message_text("❌ Канал не найден.")
            return
        text = (
            f"⚙️ Настройки @{channel.username}\n\n"
            f"Постов: {channel.total_posts_indexed}\n"
            f"Последний запуск: {channel.last_run_at or 'ещё не было'}"
        )
        await query.edit_message_text(
            text, reply_markup=channel_settings_keyboard(channel)
        )
        return

    # Set pin: setpin:{channel_id}
    if data.startswith("setpin:"):
        channel_id = int(data.split(":")[1])
        channel = queries.get_channel_by_id(channel_id)
        await query.edit_message_text(
            f"📌 Отправьте ссылку на пост в @{channel.username}, "
            f"который я буду обновлять.\n"
            f"Например: t.me/{channel.username}/123\n\n"
            f"Убедитесь, что бот добавлен админом канала."
        )
        return

    # Unpin: unpin:{channel_id}
    if data.startswith("unpin:"):
        channel_id = int(data.split(":")[1])
        queries.clear_channel_pinned(channel_id)
        await query.edit_message_text("✅ Пиннед-пост отключён.")
        return

    # Force update: force:{channel_id}
    if data.startswith("force:"):
        channel_id = int(data.split(":")[1])
        channel = queries.get_channel_by_id(channel_id)
        await query.edit_message_text(
            f"🔄 Запустите вручную:\n`python -m src.scheduler_main`\n\n"
            f"Или дождитесь следующего часового обновления.",
            parse_mode="Markdown",
        )
        return

    # Delete channel: delch:{channel_id}
    if data.startswith("delch:"):
        channel_id = int(data.split(":")[1])
        channel = queries.get_channel_by_id(channel_id)
        queries.delete_channel(channel_id)
        await query.edit_message_text(
            f"🗑 Канал @{channel.username} удалён вместе со всеми данными."
        )
        return

    logger.warning("Unhandled callback: %s", data)
