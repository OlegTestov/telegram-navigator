"""Inline keyboard callback handlers."""

import html as html_lib
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.bot.keyboards import (
    channel_actions_keyboard,
    channel_settings_keyboard,
    channels_keyboard,
    posts_keyboard,
    start_keyboard,
    subscriptions_keyboard,
    topics_keyboard,
)
from src.bot.messages import get_messages
from src.config.constants import POSTS_PER_PAGE
from src.config.settings import ADMIN_TELEGRAM_ID, get_setting, get_translation_languages
from src.services.toc_generator import generate_compact_toc, generate_translated_toc
from src.utils.helpers import truncate
from src.utils.i18n import apply_post_translations, apply_translations, get_user_lang

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
    try:
        await _route_callback(query, data, update, context)
    except (IndexError, ValueError) as e:
        logger.warning("Malformed callback data: %s (%s)", data, e)


async def _route_callback(query, data, update, context):
    """Route callback by data prefix."""
    queries = _get_queries(context)
    is_admin = update.effective_user.id == ADMIN_TELEGRAM_ID
    lang = get_user_lang(update, context)
    msg = get_messages(lang)
    content_lang = get_setting(queries, "content_language")

    if data == "noop":
        return

    # --- Settings ---

    if data == "bot_settings":
        content_lang_code = content_lang
        trans_lang_code = get_setting(queries, "translation_languages")
        digest_interval = get_setting(queries, "digest_interval_hours") or "3"

        cl_name = msg.LANG_NAME_RU if content_lang_code == "ru" else msg.LANG_NAME_EN
        tl_name = (
            msg.SETTINGS_DISABLED
            if not trans_lang_code
            else (msg.LANG_NAME_RU if trans_lang_code == "ru" else msg.LANG_NAME_EN)
        )
        ui_name = msg.LANG_NAME_RU if lang == "ru" else msg.LANG_NAME_EN

        text = msg.SETTINGS_TITLE.format(ui_lang=ui_name)
        if is_admin:
            hours_map_ru = {"1": "1 час", "3": "3 часа", "6": "6 часов", "12": "12 часов", "24": "24 часа"}
            hours_map_en = {"1": "1 hour", "3": "3 hours", "6": "6 hours", "12": "12 hours", "24": "24 hours"}
            hours_map = hours_map_ru if lang == "ru" else hours_map_en
            digest_label = hours_map.get(digest_interval, f"{digest_interval}h")
            text += msg.SETTINGS_ADMIN_SECTION.format(
                content_lang=cl_name,
                trans_lang=tl_name,
                digest_interval=digest_label,
            )

        buttons = [
            [InlineKeyboardButton(msg.KB_UI_LANG, callback_data="settings_ui_lang")],
        ]
        if is_admin:
            buttons.append([InlineKeyboardButton(msg.KB_CONTENT_LANG, callback_data="settings_content_lang")])
            buttons.append([InlineKeyboardButton(msg.KB_TRANS_LANG, callback_data="settings_trans_lang")])
            buttons.append([InlineKeyboardButton(msg.KB_DIGEST_INTERVAL, callback_data="settings_digest")])
        buttons.append([InlineKeyboardButton(msg.KB_BACK, callback_data="start")])

        await query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(buttons))
        return

    if data == "settings_ui_lang":
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("\U0001f1f7\U0001f1fa Русский", callback_data="set_ui_lang:ru"),
                    InlineKeyboardButton("\U0001f1ec\U0001f1e7 English", callback_data="set_ui_lang:en"),
                ],
                [InlineKeyboardButton(msg.KB_BACK, callback_data="bot_settings")],
            ]
        )
        await query.edit_message_text(msg.SETTINGS_CHOOSE_UI_LANG, reply_markup=kb)
        return

    if data.startswith("set_ui_lang:"):
        new_lang = data.split(":")[1]
        if new_lang not in ("ru", "en"):
            return
        queries.set_user_language(update.effective_user.id, new_lang)
        context.user_data["lang"] = new_lang
        return await _route_callback(query, "bot_settings", update, context)

    if data == "settings_content_lang" and is_admin:
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("\U0001f1ec\U0001f1e7 English", callback_data="set_content_lang:en"),
                    InlineKeyboardButton("\U0001f1f7\U0001f1fa Русский", callback_data="set_content_lang:ru"),
                ],
                [InlineKeyboardButton(msg.KB_BACK, callback_data="bot_settings")],
            ]
        )
        await query.edit_message_text(msg.SETTINGS_CHOOSE_CONTENT_LANG, reply_markup=kb)
        return

    if data.startswith("set_content_lang:") and is_admin:
        new_val = data.split(":")[1]
        if new_val not in ("ru", "en"):
            return
        # Clear translation language if it matches new content language
        current_trans = get_setting(queries, "translation_languages")
        if current_trans and current_trans == new_val:
            queries.set_bot_setting("translation_languages", "")
        queries.set_bot_setting("content_language", new_val)
        return await _route_callback(query, "bot_settings", update, context)

    if data == "settings_trans_lang" and is_admin:
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("\U0001f1ec\U0001f1e7 English", callback_data="set_trans_lang:en"),
                    InlineKeyboardButton("\U0001f1f7\U0001f1fa Русский", callback_data="set_trans_lang:ru"),
                ],
                [InlineKeyboardButton(f"🚫 {msg.SETTINGS_DISABLED}", callback_data="set_trans_lang:")],
                [InlineKeyboardButton(msg.KB_BACK, callback_data="bot_settings")],
            ]
        )
        await query.edit_message_text(msg.SETTINGS_CHOOSE_TRANS_LANG, reply_markup=kb)
        return

    if data.startswith("set_trans_lang:") and is_admin:
        new_val = data.split(":", 1)[1]
        if new_val and new_val not in ("ru", "en"):
            return
        # Don't allow translation to the same language as content
        current_content = get_setting(queries, "content_language")
        if new_val and new_val == current_content:
            new_val = ""
        queries.set_bot_setting("translation_languages", new_val)
        return await _route_callback(query, "bot_settings", update, context)

    if data == "settings_digest" and is_admin:
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("1 час" if lang == "ru" else "1 hour", callback_data="set_digest:1"),
                    InlineKeyboardButton("3 часа" if lang == "ru" else "3 hours", callback_data="set_digest:3"),
                    InlineKeyboardButton("6 часов" if lang == "ru" else "6 hours", callback_data="set_digest:6"),
                ],
                [
                    InlineKeyboardButton("12 часов" if lang == "ru" else "12 hours", callback_data="set_digest:12"),
                    InlineKeyboardButton("24 часа" if lang == "ru" else "24 hours", callback_data="set_digest:24"),
                ],
                [InlineKeyboardButton(msg.KB_BACK, callback_data="bot_settings")],
            ]
        )
        await query.edit_message_text(msg.SETTINGS_CHOOSE_DIGEST, reply_markup=kb)
        return

    if data.startswith("set_digest:") and is_admin:
        new_val = data.split(":")[1]
        if new_val in ("1", "3", "6", "12", "24"):
            queries.set_bot_setting("digest_interval_hours", new_val)
        return await _route_callback(query, "bot_settings", update, context)

    # --- Main menu ---

    if data == "open_menu":
        context.user_data.pop("search_global", None)
        context.user_data.pop("search_channel_id", None)
        has_channels = len(queries.get_active_channels()) > 0
        welcome = msg.WELCOME_ADMIN if is_admin else msg.WELCOME_USER
        await query.message.reply_text(
            welcome,
            parse_mode="HTML",
            reply_markup=start_keyboard(has_channels, is_admin, lang=lang),
        )
        return

    if data == "start":
        context.user_data.pop("search_global", None)
        context.user_data.pop("search_channel_id", None)
        has_channels = len(queries.get_active_channels()) > 0
        welcome = msg.WELCOME_ADMIN if is_admin else msg.WELCOME_USER
        await query.edit_message_text(
            welcome,
            parse_mode="HTML",
            reply_markup=start_keyboard(has_channels, is_admin, lang=lang),
        )
        return

    if data == "add_channel":
        context.user_data.pop("search_global", None)
        context.user_data.pop("search_channel_id", None)
        prompt = msg.ADD_CHANNEL_PROMPT if is_admin else msg.SUGGEST_CHANNEL_PROMPT
        back_kb = InlineKeyboardMarkup([[InlineKeyboardButton(msg.KB_BACK, callback_data="start")]])
        await query.edit_message_text(prompt, parse_mode="HTML", reply_markup=back_kb)
        return

    if data == "search_global":
        context.user_data.pop("search_channel_id", None)
        context.user_data["search_global"] = True
        back_kb = InlineKeyboardMarkup([[InlineKeyboardButton(msg.KB_BACK, callback_data="start")]])
        await query.edit_message_text(msg.SEARCH_PROMPT_GLOBAL, parse_mode="HTML", reply_markup=back_kb)
        return

    if data == "channels":
        channels = queries.get_active_channels()
        if not channels:
            await query.edit_message_text(msg.NO_CHANNELS)
            return
        await query.edit_message_text(
            msg.CHANNELS_HEADER,
            parse_mode="HTML",
            reply_markup=channels_keyboard(channels, lang=lang),
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
        kb = channel_actions_keyboard(channel_id, is_admin, has_toc, is_subscribed, lang=lang)

        if channel.cached_toc:
            # Serve translated TOC if available
            if lang != content_lang:
                toc = queries.get_toc_translation(channel_id, lang) or channel.cached_toc
            else:
                toc = channel.cached_toc
            await query.edit_message_text(
                toc,
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
        kb = channel_actions_keyboard(channel_id, is_admin, True, is_subscribed, lang=lang)

        # Skip if no new posts since last TOC
        if channel.cached_toc and hasattr(queries, "has_new_posts_since_toc"):
            if not queries.has_new_posts_since_toc(channel_id):
                if lang != content_lang:
                    toc_fresh = queries.get_toc_translation(channel_id, lang) or channel.cached_toc
                else:
                    toc_fresh = channel.cached_toc
                await query.edit_message_text(
                    toc_fresh + "\n\n" + msg.CHANNEL_STATUS_TOC_FRESH,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                    reply_markup=kb,
                )
                return

        await query.edit_message_text(msg.TOC_GENERATING)
        toc_ru, groups, post_map = await generate_compact_toc(channel, queries, content_lang)
        queries.save_cached_toc(channel_id, toc_ru)

        # Generate translated TOC for configured languages
        trans_langs = get_translation_languages(queries)
        for tlang in trans_langs:
            try:
                toc_tr = await generate_translated_toc(channel, groups, post_map, queries, lang=tlang)
                if toc_tr:
                    queries.save_toc_translation(channel_id, tlang, toc_tr)
            except Exception as e:
                logger.error("Failed to translate TOC for channel %d to %s: %s", channel_id, tlang, e)

        # Show the user their language version
        if lang != content_lang:
            toc = queries.get_toc_translation(channel_id, lang) or toc_ru
        else:
            toc = toc_ru
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
        if lang != content_lang:
            tr = queries.get_topic_translations([t.id for t in topics], lang)
            apply_translations(topics, tr, ["name", "summary"])
        await query.edit_message_text(
            msg.TOPICS_HEADER,
            parse_mode="HTML",
            reply_markup=topics_keyboard(topics, channel_id, page, lang=lang),
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

        # Apply translations for non-Russian users
        if lang != content_lang:
            tr = queries.get_topic_translations([topic.id], lang)
            apply_translations([topic], tr, ["name", "summary"])
            post_tr = queries.get_post_translations([p.id for p in posts], lang)
            apply_post_translations(posts, post_tr)

        emoji = topic.emoji or "\U0001f4cc"
        posts_word = msg.TOPIC_POSTS_SUFFIX
        lines = [f"{emoji} <b>{html_lib.escape(topic.name)}</b> ({total} {posts_word})"]
        if topic.summary:
            lines.append(f"<i>{html_lib.escape(topic.summary)}</i>")
        lines.append("")

        for i, post in enumerate(posts, start=page * POSTS_PER_PAGE + 1):
            desc = html_lib.escape(post.description or truncate(post.text, 60))
            lines.append(f'{i}. <a href="{post.post_url}">{desc}</a>')

        text = "\n".join(lines)
        if len(text) > 4000:
            text = text[:4000] + "\n..."

        await query.edit_message_text(
            text,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=posts_keyboard(posts, channel_id, slug, page, total, lang=lang),
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
            back_kb = InlineKeyboardMarkup([[InlineKeyboardButton(msg.KB_BACK, callback_data="start")]])
            await query.edit_message_text(
                msg.SUBS_EMPTY,
                parse_mode="HTML",
                reply_markup=back_kb,
            )
            return
        subs = queries.get_user_subscriptions(user_id)
        subscribed_ids = {ch.id for ch in subs}
        await query.edit_message_text(
            msg.SUBS_HEADER,
            parse_mode="HTML",
            reply_markup=subscriptions_keyboard(channels, subscribed_ids, lang=lang),
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
            msg.SUBS_HEADER,
            parse_mode="HTML",
            reply_markup=subscriptions_keyboard(channels, subscribed_ids, lang=lang),
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
        kb = channel_actions_keyboard(channel_id, is_admin, has_toc, is_subscribed=True, lang=lang)
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
        kb = channel_actions_keyboard(channel_id, is_admin, has_toc, is_subscribed=False, lang=lang)
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
            last_run=channel.last_run_at or "---",
        )
        await query.edit_message_text(
            text, parse_mode="HTML", reply_markup=channel_settings_keyboard(channel, lang=lang)
        )
        return

    if data.startswith("setpin:"):
        if not is_admin:
            await query.edit_message_text(msg.NOT_ADMIN)
            return
        channel_id = int(data.split(":")[1])
        channel = queries.get_channel_by_id(channel_id)
        await query.edit_message_text(msg.PINNED_PROMPT.format(username=channel.username))
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
        await query.edit_message_text(msg.CHANNEL_DELETED.format(username=channel.username))
        return

    logger.warning("Unhandled callback: %s", data)
