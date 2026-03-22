"""Fetch posts from Telegram channels via Telethon."""

import logging
from datetime import timezone
from telethon import TelegramClient
from telethon.sessions import StringSession

from src.config.settings import TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_SESSION_STRING
from src.utils.errors import FetchError

logger = logging.getLogger(__name__)


def create_telethon_client() -> TelegramClient:
    """Create a Telethon client using StringSession."""
    return TelegramClient(
        StringSession(TELEGRAM_SESSION_STRING),
        TELEGRAM_API_ID,
        TELEGRAM_API_HASH,
    )


async def fetch_channel_posts(
    client: TelegramClient,
    channel_username: str,
    last_message_id: int = 0,
) -> tuple[str, list[dict]]:
    """Fetch posts from a channel newer than last_message_id.

    Returns (channel_title, list of post dicts).
    """
    try:
        entity = await client.get_entity(channel_username)
        title = getattr(entity, "title", channel_username)
        posts = []

        async for message in client.iter_messages(entity, limit=None):
            if message.id <= last_message_id:
                break

            text = message.text or ""
            if not text.strip():
                continue

            msg_date = message.date
            if msg_date and msg_date.tzinfo is None:
                msg_date = msg_date.replace(tzinfo=timezone.utc)

            # Engagement metrics
            views = message.views or 0
            forwards = message.forwards or 0
            reactions_count = 0
            if message.reactions and message.reactions.results:
                reactions_count = sum(r.count for r in message.reactions.results)

            posts.append({
                "message_id": message.id,
                "text": text,
                "post_date": msg_date.isoformat(),
                "post_url": f"https://t.me/{channel_username}/{message.id}",
                "has_media": message.media is not None,
                "views": views,
                "forwards": forwards,
                "reactions_count": reactions_count,
            })

        logger.info(
            "Fetched %d new posts from @%s (after msg_id=%d)",
            len(posts), channel_username, last_message_id,
        )
        return title, posts

    except Exception as e:
        logger.error("Error fetching @%s: %s", channel_username, e)
        raise FetchError(f"Failed to fetch @{channel_username}: {e}") from e
