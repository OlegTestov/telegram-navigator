"""Inline keyboard builders."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.bot.messages import get_messages
from src.config.constants import POSTS_PER_PAGE, TOPICS_PER_PAGE
from src.database.models import Channel, Post, Topic


def search_results_keyboard(channel_id: int = None, lang: str = "ru") -> InlineKeyboardMarkup:
    """Buttons after search results."""
    msg = get_messages(lang)
    search_cb = f"search:{channel_id}" if channel_id else "search_global"
    back_cb = f"ch:{channel_id}" if channel_id else "start"
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(msg.KB_NEW_SEARCH, callback_data=search_cb),
                InlineKeyboardButton(msg.KB_BACK, callback_data=back_cb),
            ],
        ]
    )


def start_keyboard(has_channels: bool, is_admin: bool = False, lang: str = "ru") -> InlineKeyboardMarkup:
    """Start screen keyboard — 2x2 grid."""
    msg = get_messages(lang)
    add_label = msg.KB_ADD_CHANNEL if is_admin else msg.KB_SUGGEST
    if has_channels:
        buttons = [
            [
                InlineKeyboardButton(msg.KB_SEARCH, callback_data="search_global"),
                InlineKeyboardButton(msg.KB_SUBSCRIPTIONS, callback_data="my_subs"),
            ],
            [
                InlineKeyboardButton(msg.KB_CHANNELS, callback_data="channels"),
                InlineKeyboardButton(add_label, callback_data="add_channel"),
            ],
        ]
    else:
        buttons = [
            [InlineKeyboardButton(add_label, callback_data="add_channel")],
            [InlineKeyboardButton(msg.KB_SUBSCRIPTIONS, callback_data="my_subs")],
        ]
    buttons.append([InlineKeyboardButton(msg.KB_BOT_SETTINGS, callback_data="bot_settings")])
    return InlineKeyboardMarkup(buttons)


def channels_keyboard(channels: list[Channel], lang: str = "ru") -> InlineKeyboardMarkup:
    """Build keyboard with list of channels, 2 per row."""
    msg = get_messages(lang)
    buttons = []
    row = []
    for ch in channels:
        label = f"\U0001f4e2 {ch.title or ch.username}"
        if ch.total_posts_indexed > 0:
            label += f" ({ch.total_posts_indexed})"
        row.append(InlineKeyboardButton(label, callback_data=f"ch:{ch.id}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(msg.KB_BACK, callback_data="start")])
    return InlineKeyboardMarkup(buttons)


def channel_actions_keyboard(
    channel_id: int,
    is_admin: bool = False,
    has_toc: bool = False,
    is_subscribed: bool = False,
    lang: str = "ru",
) -> InlineKeyboardMarkup:
    """Actions for a selected channel — 2 columns, 3 rows."""
    msg = get_messages(lang)
    toc_label = msg.KB_REFRESH_TOC if has_toc else msg.KB_CREATE_TOC
    sub_label = msg.KB_UNSUBSCRIBE if is_subscribed else msg.KB_SUBSCRIBE
    sub_cb = f"unsub:{channel_id}" if is_subscribed else f"sub:{channel_id}"
    buttons = [
        [
            InlineKeyboardButton(msg.KB_SEARCH, callback_data=f"search:{channel_id}"),
            InlineKeyboardButton(msg.KB_ALL_TOPICS, callback_data=f"topics:{channel_id}:0"),
        ],
        [
            InlineKeyboardButton(sub_label, callback_data=sub_cb),
            InlineKeyboardButton(toc_label, callback_data=f"toc:{channel_id}"),
        ],
    ]
    if is_admin:
        buttons.append(
            [
                InlineKeyboardButton(msg.KB_SETTINGS, callback_data=f"settings:{channel_id}"),
                InlineKeyboardButton(msg.KB_BACK, callback_data="channels"),
            ]
        )
    else:
        buttons.append([InlineKeyboardButton(msg.KB_BACK, callback_data="channels")])
    return InlineKeyboardMarkup(buttons)


def topics_keyboard(
    topics: list[Topic],
    channel_id: int,
    page: int = 0,
    lang: str = "ru",
) -> InlineKeyboardMarkup:
    """Build paginated topics keyboard."""
    msg = get_messages(lang)
    start = page * TOPICS_PER_PAGE
    end = start + TOPICS_PER_PAGE
    page_topics = topics[start:end]
    total_pages = (len(topics) + TOPICS_PER_PAGE - 1) // TOPICS_PER_PAGE

    buttons = []
    row = []
    for topic in page_topics:
        emoji = topic.emoji or "\U0001f4cc"
        label = f"{emoji} {topic.name} ({topic.post_count})"
        row.append(InlineKeyboardButton(label, callback_data=f"topic:{channel_id}:{topic.slug}:0"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"topics:{channel_id}:{page - 1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"topics:{channel_id}:{page + 1}"))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton(msg.KB_TO_CHANNEL, callback_data=f"ch:{channel_id}")])
    return InlineKeyboardMarkup(buttons)


def posts_keyboard(
    posts: list[Post],
    channel_id: int,
    topic_slug: str,
    page: int,
    total_count: int,
    lang: str = "ru",
) -> InlineKeyboardMarkup:
    """Navigation for posts list."""
    msg = get_messages(lang)
    total_pages = (total_count + POSTS_PER_PAGE - 1) // POSTS_PER_PAGE
    buttons = []

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"topic:{channel_id}:{topic_slug}:{page - 1}"))
    nav.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"topic:{channel_id}:{topic_slug}:{page + 1}"))
    buttons.append(nav)

    buttons.append([InlineKeyboardButton(msg.KB_TO_TOPICS, callback_data=f"topics:{channel_id}:0")])
    return InlineKeyboardMarkup(buttons)


def subscriptions_keyboard(
    channels: list[Channel],
    subscribed_ids: set[int],
    lang: str = "ru",
) -> InlineKeyboardMarkup:
    """All channels with toggle subscribe/unsubscribe."""
    msg = get_messages(lang)
    buttons = []
    row = []
    for ch in channels:
        name = ch.title or ch.username
        label = f"✅ {name}" if ch.id in subscribed_ids else f"◻️ {name}"
        row.append(InlineKeyboardButton(label, callback_data=f"toggle_sub:{ch.id}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(msg.KB_BACK, callback_data="start")])
    return InlineKeyboardMarkup(buttons)


def channel_settings_keyboard(channel: Channel, lang: str = "ru") -> InlineKeyboardMarkup:
    """Settings for a channel (admin only)."""
    msg = get_messages(lang)
    buttons = []
    if channel.pinned_message_id:
        buttons.append(
            [
                InlineKeyboardButton(
                    msg.KB_PINNED_STATUS.format(id=channel.pinned_message_id),
                    callback_data=f"unpin:{channel.id}",
                )
            ]
        )
    else:
        buttons.append(
            [
                InlineKeyboardButton(
                    msg.KB_SET_PINNED,
                    callback_data=f"setpin:{channel.id}",
                )
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(msg.KB_FORCE_UPDATE, callback_data=f"force:{channel.id}"),
        ]
    )
    buttons.append(
        [
            InlineKeyboardButton(msg.KB_DELETE_CHANNEL, callback_data=f"delch:{channel.id}"),
        ]
    )
    buttons.append(
        [
            InlineKeyboardButton(msg.KB_BACK, callback_data=f"ch:{channel.id}"),
        ]
    )
    return InlineKeyboardMarkup(buttons)
