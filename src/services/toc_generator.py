"""Generate compact Table of Contents for a channel."""

import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta

from google import genai

from src.database.models import Channel, Post
from src.config.settings import GEMINI_API_KEY, GEMINI_MODEL
from src.config.constants import (
    TOC_MAX_LENGTH,
    TOC_GROUPS_COUNT,
    TOC_POSTS_PER_GROUP,
    TOC_POSTS_PERIOD_DAYS,
    MAX_POST_TEXT_FOR_LLM,
)
from src.config.prompts import TOC_GROUPING_PROMPT
from src.utils.helpers import content_hash, truncate

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


GROUP_EMOJIS = ["🤖", "📰", "🛠", "💡", "🚀", "📊", "🧠", "🎯"]


async def generate_toc_groups(
    posts: list[Post],
    tags_map: dict[int, list[str]] | None = None,
) -> list[dict]:
    """Use Gemini to split posts into non-overlapping groups.

    Args:
        posts: List of posts to group.
        tags_map: Optional {message_id: [tag1, tag2, ...]} for better grouping.

    Returns list of {"group_name": str, "post_ids": list[int]}.
    """
    if not posts:
        return []

    # Build posts list for prompt — include tags if available
    posts_text = []
    for post in posts:
        desc = post.description or truncate(post.text, 80)
        tags = tags_map.get(post.message_id, []) if tags_map else []
        tags_str = f" [{', '.join(tags)}]" if tags else ""
        posts_text.append(f"[{post.message_id}] {desc}{tags_str}")

    prompt = TOC_GROUPING_PROMPT.format(
        groups_count=TOC_GROUPS_COUNT,
        posts="\n".join(posts_text),
    )

    try:
        c = _get_client()
        response = await asyncio.to_thread(
            c.models.generate_content,
            model=GEMINI_MODEL,
            contents=prompt,
        )
        return _parse_grouping_response(response.text)
    except Exception as e:
        logger.error("TOC grouping error: %s", e)
        return _fallback_grouping(posts)


def _parse_grouping_response(text: str) -> list[dict]:
    """Parse JSON grouping response from Gemini."""
    text = text.strip()
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON array in response: {text[:200]}")

    data = json.loads(text[start : end + 1])
    groups = []
    for item in data:
        groups.append({
            "group_name": item["group_name"],
            "post_ids": [int(pid) for pid in item["post_ids"]],
        })
    return groups


def _fallback_grouping(posts: list[Post]) -> list[dict]:
    """Simple fallback: split posts into groups by chronological order."""
    chunk_size = max(1, len(posts) // TOC_GROUPS_COUNT)
    groups = []
    sorted_posts = sorted(posts, key=lambda p: p.score, reverse=True)
    for i in range(TOC_GROUPS_COUNT):
        chunk = sorted_posts[i * chunk_size : (i + 1) * chunk_size]
        if chunk:
            groups.append({
                "group_name": f"Группа {i + 1}",
                "post_ids": [p.message_id for p in chunk],
            })
    return groups


async def generate_compact_toc(channel: Channel, queries) -> str:
    """Generate compact TOC with expandable blockquotes (up to 4000 chars).

    Uses Gemini to group posts into ~5 non-overlapping categories.
    Each category rendered as expandable blockquote with top posts as inline links.
    """
    # Get posts from the last year
    cutoff = datetime.now(timezone.utc) - timedelta(days=TOC_POSTS_PERIOD_DAYS)
    all_posts = queries.get_posts_since(channel.id, cutoff.isoformat())

    if not all_posts:
        return f"📚 Оглавление @{channel.username}\n\nПока нет проиндексированных постов."

    # Get tags for better grouping
    tags_map = queries.get_tags_for_posts(channel.id)

    # Group posts via Gemini (with tags for context)
    groups = await generate_toc_groups(all_posts, tags_map)
    if not groups:
        return f"📚 Оглавление @{channel.username}\n\nНе удалось сгруппировать посты."

    # Build post lookup by message_id
    post_map = {p.message_id: p for p in all_posts}

    date_str = datetime.now(timezone.utc).strftime("%d.%m.%Y")
    header = f'<b>📚 Оглавление @{channel.username}</b>\nОбновлено: {date_str}\n'

    sections = []
    chars_used = len(header)
    used_post_ids = set()  # prevent duplicates across groups

    for i, group in enumerate(groups):
        emoji = GROUP_EMOJIS[i % len(GROUP_EMOJIS)]
        group_name = group["group_name"]

        # Get posts for this group, sorted by score, deduplicated
        seen_ids = set()
        group_posts = []
        for pid in group["post_ids"]:
            if pid in post_map and pid not in seen_ids and pid not in used_post_ids:
                group_posts.append(post_map[pid])
                seen_ids.add(pid)
        group_posts.sort(key=lambda p: p.score, reverse=True)
        top_posts = group_posts[:TOC_POSTS_PER_GROUP]
        used_post_ids.update(p.message_id for p in top_posts)

        if not top_posts:
            continue

        total_in_group = len(group_posts)

        # Build post lines with inline links
        post_lines = []
        for j, post in enumerate(top_posts, 1):
            desc = truncate(post.description or post.text, 50)
            # Escape HTML special chars in description
            desc = desc.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            line = f'{j}. <a href="{post.post_url}">{desc}</a>'
            post_lines.append(line)

        blockquote_content = "\n".join(post_lines)
        section = (
            f'\n<b>{emoji} {group_name}</b> ({total_in_group})\n'
            f'<blockquote expandable>{blockquote_content}</blockquote>'
        )

        # Check if we exceed limit
        if chars_used + len(section) > TOC_MAX_LENGTH:
            # Try with fewer posts
            for trim in range(len(post_lines) - 1, 2, -1):
                trimmed = "\n".join(post_lines[:trim])
                section = (
                    f'\n<b>{emoji} {group_name}</b> ({total_in_group})\n'
                    f'<blockquote expandable>{trimmed}</blockquote>'
                )
                if chars_used + len(section) <= TOC_MAX_LENGTH:
                    break
            else:
                break  # Can't fit even 3 posts, stop adding groups

        sections.append(section)
        chars_used += len(section)

    toc = header + "".join(sections)

    if len(toc) > TOC_MAX_LENGTH:
        toc = toc[:TOC_MAX_LENGTH - 1] + "…"

    return toc


def should_update_pinned(channel: Channel, new_toc: str) -> bool:
    """Check if pinned post needs updating."""
    if not channel.pinned_message_id or not channel.pinned_chat_id:
        return False
    new_hash = content_hash(new_toc)
    return new_hash != channel.pinned_content_hash
