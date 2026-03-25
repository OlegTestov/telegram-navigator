"""Inline keyboard builders."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.database.models import Channel, Topic, Post
from src.config.constants import TOPICS_PER_PAGE, POSTS_PER_PAGE


def search_results_keyboard(channel_id: int = None) -> InlineKeyboardMarkup:
    """Buttons after search results."""
    search_cb = f"search:{channel_id}" if channel_id else "search_global"
    back_cb = f"ch:{channel_id}" if channel_id else "start"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔍 Новый поиск", callback_data=search_cb),
            InlineKeyboardButton("🔙 Назад", callback_data=back_cb),
        ],
    ])


def start_keyboard(has_channels: bool, is_admin: bool = False) -> InlineKeyboardMarkup:
    """Start screen keyboard — 2x2 grid."""
    add_label = "➕ Добавить канал" if is_admin else "📨 Предложить канал"
    if has_channels:
        buttons = [
            [
                InlineKeyboardButton("🔍 Поиск", callback_data="search_global"),
                InlineKeyboardButton("📬 Подписки", callback_data="my_subs"),
            ],
            [
                InlineKeyboardButton("📢 Каналы", callback_data="channels"),
                InlineKeyboardButton(add_label, callback_data="add_channel"),
            ],
        ]
    else:
        buttons = [
            [InlineKeyboardButton(add_label, callback_data="add_channel")],
            [InlineKeyboardButton("📬 Подписки", callback_data="my_subs")],
        ]
    return InlineKeyboardMarkup(buttons)


def channels_keyboard(channels: list[Channel]) -> InlineKeyboardMarkup:
    """Build keyboard with list of channels, 2 per row."""
    buttons = []
    row = []
    for ch in channels:
        label = f"📢 {ch.username}"
        if ch.total_posts_indexed > 0:
            label += f" ({ch.total_posts_indexed})"
        row.append(InlineKeyboardButton(label, callback_data=f"ch:{ch.id}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="start")])
    return InlineKeyboardMarkup(buttons)


def channel_actions_keyboard(
    channel_id: int, is_admin: bool = False, has_toc: bool = False,
    is_subscribed: bool = False,
) -> InlineKeyboardMarkup:
    """Actions for a selected channel — 2 columns, 3 rows."""
    toc_label = "🔄 Обновить оглавление" if has_toc else "📚 Создать оглавление"
    sub_label = "📭 Отписаться" if is_subscribed else "📬 Подписаться"
    sub_cb = f"unsub:{channel_id}" if is_subscribed else f"sub:{channel_id}"
    buttons = [
        [
            InlineKeyboardButton("🔍 Поиск", callback_data=f"search:{channel_id}"),
            InlineKeyboardButton("📋 Все темы", callback_data=f"topics:{channel_id}:0"),
        ],
        [
            InlineKeyboardButton(sub_label, callback_data=sub_cb),
            InlineKeyboardButton(toc_label, callback_data=f"toc:{channel_id}"),
        ],
    ]
    if is_admin:
        buttons.append([
            InlineKeyboardButton("⚙️ Настройки", callback_data=f"settings:{channel_id}"),
            InlineKeyboardButton("🔙 Назад", callback_data="channels"),
        ])
    else:
        buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="channels")])
    return InlineKeyboardMarkup(buttons)


def topics_keyboard(
    topics: list[Topic], channel_id: int, page: int = 0
) -> InlineKeyboardMarkup:
    """Build paginated topics keyboard."""
    start = page * TOPICS_PER_PAGE
    end = start + TOPICS_PER_PAGE
    page_topics = topics[start:end]
    total_pages = (len(topics) + TOPICS_PER_PAGE - 1) // TOPICS_PER_PAGE

    buttons = []
    row = []
    for topic in page_topics:
        emoji = topic.emoji or "📌"
        label = f"{emoji} {topic.name} ({topic.post_count})"
        row.append(
            InlineKeyboardButton(label, callback_data=f"topic:{channel_id}:{topic.slug}:0")
        )
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

    buttons.append([InlineKeyboardButton("🔙 К каналу", callback_data=f"ch:{channel_id}")])
    return InlineKeyboardMarkup(buttons)


def posts_keyboard(
    posts: list[Post],
    channel_id: int,
    topic_slug: str,
    page: int,
    total_count: int,
) -> InlineKeyboardMarkup:
    """Navigation for posts list."""
    total_pages = (total_count + POSTS_PER_PAGE - 1) // POSTS_PER_PAGE
    buttons = []

    nav = []
    if page > 0:
        nav.append(
            InlineKeyboardButton("⬅️", callback_data=f"topic:{channel_id}:{topic_slug}:{page - 1}")
        )
    nav.append(
        InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop")
    )
    if page < total_pages - 1:
        nav.append(
            InlineKeyboardButton("➡️", callback_data=f"topic:{channel_id}:{topic_slug}:{page + 1}")
        )
    buttons.append(nav)

    buttons.append([
        InlineKeyboardButton("🔙 К темам", callback_data=f"topics:{channel_id}:0")
    ])
    return InlineKeyboardMarkup(buttons)


def subscriptions_keyboard(
    channels: list[Channel], subscribed_ids: set[int],
) -> InlineKeyboardMarkup:
    """All channels with toggle subscribe/unsubscribe."""
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
    buttons.append([InlineKeyboardButton("🔙 Назад", callback_data="start")])
    return InlineKeyboardMarkup(buttons)


def channel_settings_keyboard(channel: Channel) -> InlineKeyboardMarkup:
    """Settings for a channel (admin only)."""
    buttons = []
    if channel.pinned_message_id:
        buttons.append([
            InlineKeyboardButton(
                f"📌 Пиннед: пост #{channel.pinned_message_id}",
                callback_data=f"unpin:{channel.id}",
            )
        ])
    else:
        buttons.append([
            InlineKeyboardButton(
                "📌 Настроить пиннед-пост",
                callback_data=f"setpin:{channel.id}",
            )
        ])
    buttons.append([
        InlineKeyboardButton("🔄 Обновить сейчас", callback_data=f"force:{channel.id}"),
    ])
    buttons.append([
        InlineKeyboardButton("🗑 Удалить канал", callback_data=f"delch:{channel.id}"),
    ])
    buttons.append([
        InlineKeyboardButton("🔙 Назад", callback_data=f"ch:{channel.id}"),
    ])
    return InlineKeyboardMarkup(buttons)
