"""Inline keyboard callback handlers."""

import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.config.settings import ADMIN_TELEGRAM_ID
from src.bot import messages as msg
from src.bot.keyboards import (
    start_keyboard,
    channels_keyboard,
    channel_actions_keyboard,
    topics_keyboard,
    posts_keyboard,
    channel_settings_keyboard,
    subscriptions_keyboard,
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
    try:
        await query.answer()
    except Exception:
        pass

    data = query.data
    queries = _get_queries(context)
    is_admin = update.effective_user.id == ADMIN_TELEGRAM_ID

    if data == "noop":
        return

    if data == "start":
        context.user_data.pop("search_global", None)
        context.user_data.pop("search_channel_id", None)
        has_channels = len(queries.get_active_channels()) > 0
        welcome = msg.WELCOME_ADMIN if is_admin else msg.WELCOME_USER
        await query.edit_message_text(
            welcome, parse_mode="HTML",
            reply_markup=start_keyboard(has_channels, is_admin),
        )
        return

    if data == "add_channel":
        context.user_data.pop("search_global", None)
        context.user_data.pop("search_channel_id", None)
        prompt = msg.ADD_CHANNEL_PROMPT if is_admin else msg.SUGGEST_CHANNEL_PROMPT
        back_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад", callback_data="start")]
        ])
        await query.edit_message_text(prompt, parse_mode="HTML", reply_markup=back_kb)
        return

    if data == "search_global":
        context.user_data.pop("search_channel_id", None)
        context.user_data["search_global"] = True
        back_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Назад", callback_data="start")]
        ])
        await query.edit_message_text(msg.SEARCH_PROMPT_GLOBAL, parse_mode="HTML", reply_markup=back_kb)
        return

    if data == "channels":
        channels = queries.get_active_channels()
        if not channels:
            await query.edit_message_text(msg.NO_CHANNELS)
            return
        await query.edit_message_text(
            msg.CHANNELS_HEADER, parse_mode="HTML",
            reply_markup=channels_keyboard(channels),
        )
        return

    # Channel selected: ch:{channel_id}
    if data.startswith("ch:"):
        channel_id = int(data.split(":")[1])
        channel = queries.get_channel_by_id(channel_id)
        if not channel:
            await query.edit_message_text(msg.CHANNEL_ERROR)
            return

        has_toc = bool(channel.cached_toc)
        user_id = update.effective_user.id
        is_subscribed = queries.is_user_subscribed(user_id, channel_id)
        kb = channel_actions_keyboard(channel_id, is_admin, has_toc, is_subscribed)

        if channel.cached_toc:
            await query.edit_message_text(
                channel.cached_toc,
                parse_mode="HTML",
                disable_web_page_preview=True,
                reply_markup=kb,
            )
        else:
            post_count = queries.get_channel_post_count(channel_id)
            topic_count = len(queries.get_topics(channel_id))
            if post_count == 0:
                status = msg.CHANNEL_STATUS_NOT_INDEXED
            else:
                status = msg.CHANNEL_STATUS_NO_TOC
            text = msg.CHANNEL_INFO.format(
                username=channel.username,
                post_count=post_count,
                topic_count=topic_count,
                status=status,
            )
            await query.edit_message_text(text, parse_mode="HTML", reply_markup=kb)
        return

    # Generate/refresh TOC: toc:{channel_id}
    if data.startswith("toc:"):
        channel_id = int(data.split(":")[1])
        channel = queries.get_channel_by_id(channel_id)
        if not channel:
            await query.edit_message_text(msg.CHANNEL_ERROR)
            return

        user_id = update.effective_user.id
        is_subscribed = queries.is_user_subscribed(user_id, channel_id)
        kb = channel_actions_keyboard(channel_id, is_admin, True, is_subscribed)

        # Skip if no new posts since last TOC
        if channel.cached_toc and hasattr(queries, "has_new_posts_since_toc"):
            if not queries.has_new_posts_since_toc(channel_id):
                await query.edit_message_text(
                    channel.cached_toc + "\n\n" + msg.CHANNEL_STATUS_TOC_FRESH,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                    reply_markup=kb,
                )
                return

        await query.edit_message_text(msg.TOC_GENERATING)
        toc = await generate_compact_toc(channel, queries)
        queries.save_cached_toc(channel_id, toc)
        await query.edit_message_text(
            toc,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=kb,
        )
        return

    # Topics list: topics:{channel_id}:{page}
    if data.startswith("topics:"):
        parts = data.split(":")
        channel_id = int(parts[1])
        page = int(parts[2])
        topics = queries.get_topics(channel_id)
        if not topics:
            await query.edit_message_text(msg.NO_TOPICS)
            return
        await query.edit_message_text(
            msg.TOPICS_HEADER, parse_mode="HTML",
            reply_markup=topics_keyboard(topics, channel_id, page),
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
            await query.edit_message_text(msg.TOPIC_NOT_FOUND)
            return

        posts = queries.get_posts_by_topic(topic.id, page=page, limit=POSTS_PER_PAGE)
        total = queries.get_topic_post_count(topic.id)

        emoji = topic.emoji or "📌"
        lines = [f"{emoji} <b>{topic.name}</b> ({total} постов)"]
        if topic.summary:
            lines.append(f"<i>{topic.summary}</i>")
        lines.append("")

        for i, post in enumerate(posts, start=page * POSTS_PER_PAGE + 1):
            desc = post.description or truncate(post.text, 60)
            lines.append(f'{i}. <a href="{post.post_url}">{desc}</a>')

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
        context.user_data.pop("search_global", None)
        context.user_data["search_channel_id"] = channel_id
        await query.edit_message_text(msg.SEARCH_PROMPT_CHANNEL)
        return

    # --- Subscriptions ---

    if data == "my_subs":
        user_id = update.effective_user.id
        channels = queries.get_active_channels()
        if not channels:
            back_kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data="start")]
            ])
            await query.edit_message_text(
                msg.SUBS_EMPTY, parse_mode="HTML", reply_markup=back_kb,
            )
            return
        subs = queries.get_user_subscriptions(user_id)
        subscribed_ids = {ch.id for ch in subs}
        await query.edit_message_text(
            msg.SUBS_HEADER, parse_mode="HTML",
            reply_markup=subscriptions_keyboard(channels, subscribed_ids),
        )
        return

    if data.startswith("toggle_sub:"):
        channel_id = int(data.split(":")[1])
        user_id = update.effective_user.id
        if queries.is_user_subscribed(user_id, channel_id):
            queries.unsubscribe_user(user_id, channel_id)
        else:
            queries.subscribe_user(user_id, channel_id)
        # Re-render the same screen
        channels = queries.get_active_channels()
        subs = queries.get_user_subscriptions(user_id)
        subscribed_ids = {ch.id for ch in subs}
        await query.edit_message_text(
            msg.SUBS_HEADER, parse_mode="HTML",
            reply_markup=subscriptions_keyboard(channels, subscribed_ids),
        )
        return

    if data.startswith("sub:"):
        channel_id = int(data.split(":")[1])
        channel = queries.get_channel_by_id(channel_id)
        if not channel:
            await query.edit_message_text(msg.CHANNEL_ERROR)
            return
        user_id = update.effective_user.id
        queries.subscribe_user(user_id, channel_id)
        has_toc = bool(channel.cached_toc)
        kb = channel_actions_keyboard(channel_id, is_admin, has_toc, is_subscribed=True)
        text = msg.SUBSCRIBED.format(username=channel.username)
        await query.edit_message_text(text, reply_markup=kb)
        return

    if data.startswith("unsub:"):
        channel_id = int(data.split(":")[1])
        channel = queries.get_channel_by_id(channel_id)
        if not channel:
            await query.edit_message_text(msg.CHANNEL_ERROR)
            return
        user_id = update.effective_user.id
        queries.unsubscribe_user(user_id, channel_id)
        has_toc = bool(channel.cached_toc)
        kb = channel_actions_keyboard(channel_id, is_admin, has_toc, is_subscribed=False)
        text = msg.UNSUBSCRIBED.format(username=channel.username)
        await query.edit_message_text(text, reply_markup=kb)
        return

    # --- Admin-only callbacks below ---

    if data.startswith("settings:"):
        if not is_admin:
            await query.edit_message_text(msg.NOT_ADMIN)
            return
        channel_id = int(data.split(":")[1])
        channel = queries.get_channel_by_id(channel_id)
        if not channel:
            await query.edit_message_text(msg.CHANNEL_ERROR)
            return
        text = msg.SETTINGS_INFO.format(
            username=channel.username,
            total_posts=channel.total_posts_indexed,
            last_run=channel.last_run_at or "ещё не было",
        )
        await query.edit_message_text(
            text, parse_mode="HTML", reply_markup=channel_settings_keyboard(channel)
        )
        return

    if data.startswith("setpin:"):
        if not is_admin:
            await query.edit_message_text(msg.NOT_ADMIN)
            return
        channel_id = int(data.split(":")[1])
        channel = queries.get_channel_by_id(channel_id)
        await query.edit_message_text(
            msg.PINNED_PROMPT.format(username=channel.username)
        )
        return

    if data.startswith("unpin:"):
        if not is_admin:
            await query.edit_message_text(msg.NOT_ADMIN)
            return
        channel_id = int(data.split(":")[1])
        queries.clear_channel_pinned(channel_id)
        await query.edit_message_text(msg.PINNED_CLEARED)
        return

    if data.startswith("force:"):
        if not is_admin:
            await query.edit_message_text(msg.NOT_ADMIN)
            return
        await query.edit_message_text(msg.FORCE_UPDATE_INFO, parse_mode="HTML")
        return

    if data.startswith("delch:"):
        if not is_admin:
            await query.edit_message_text(msg.NOT_ADMIN)
            return
        channel_id = int(data.split(":")[1])
        channel = queries.get_channel_by_id(channel_id)
        queries.delete_channel(channel_id)
        await query.edit_message_text(
            msg.CHANNEL_DELETED.format(username=channel.username)
        )
        return

    logger.warning("Unhandled callback: %s", data)
