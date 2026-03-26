"""Fetch posts from Telegram channels via Telethon."""

import logging
from datetime import timezone
from typing import Optional

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import InputPeerChannel

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


async def _collect_posts(client, entity, channel_username, last_message_id):
    """Iterate messages and collect text posts."""
    posts = []
    async for message in client.iter_messages(
        entity, min_id=last_message_id, limit=500
    ):
        text = message.text or ""
        if not text.strip():
            continue

        msg_date = message.date
        if msg_date and msg_date.tzinfo is None:
            msg_date = msg_date.replace(tzinfo=timezone.utc)

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
    return posts


async def fetch_channel_posts(
    client: TelegramClient,
    channel_username: str,
    last_message_id: int = 0,
    peer_id: Optional[int] = None,
    access_hash: Optional[int] = None,
) -> tuple[str, list[dict], int, int]:
    """Fetch posts from a channel newer than last_message_id.

    Fast path: InputPeerChannel(peer_id, access_hash) — zero API overhead.
    Fallback: username resolution (1 API call) if first run or stale credentials.

    Returns (title_or_none, posts, peer_id, access_hash).
    """
    try:
        resolved_by_username = False

        if peer_id and access_hash:
            try:
                entity = InputPeerChannel(peer_id, access_hash)
                posts = await _collect_posts(client, entity, channel_username, last_message_id)
            except Exception as e:
                logger.warning("InputPeerChannel failed for @%s, resolving by username: %s", channel_username, e)
                entity = await client.get_entity(channel_username)
                resolved_by_username = True
                posts = await _collect_posts(client, entity, channel_username, last_message_id)
        else:
            entity = await client.get_entity(channel_username)
            resolved_by_username = True
            posts = await _collect_posts(client, entity, channel_username, last_message_id)

        if resolved_by_username:
            out_peer_id = entity.id
            out_access_hash = getattr(entity, "access_hash", None)
            title = getattr(entity, "title", channel_username)
        else:
            out_peer_id = peer_id
            out_access_hash = access_hash
            title = None  # use DB title

        logger.info("Fetched %d new posts from @%s (after msg_id=%d)", len(posts), channel_username, last_message_id)
        return title, posts, out_peer_id, out_access_hash

    except Exception as e:
        logger.error("Error fetching @%s: %s", channel_username, e)
        raise FetchError(f"Failed to fetch @{channel_username}: {e}") from e
