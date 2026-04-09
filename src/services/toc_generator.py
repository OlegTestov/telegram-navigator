"""Generate compact Table of Contents for a channel."""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from google import genai

from src.bot.messages import get_messages
from src.config.constants import (
    TOC_GROUPS_COUNT,
    TOC_MAX_LENGTH,
    TOC_POSTS_PER_GROUP,
    TOC_POSTS_PERIOD_DAYS,
)
from src.config.prompts import TOC_GROUPING_PROMPT, get_language_config
from src.config.settings import GEMINI_API_KEY, GEMINI_MODEL
from src.database.models import Channel, Post
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
    content_language: str = "en",
) -> list[dict]:
    """Use Gemini to split posts into non-overlapping groups.

    Args:
        posts: List of posts to group.
        tags_map: Optional {message_id: [tag1, tag2, ...]} for better grouping.
        content_language: Language for group names.

    Returns list of {"group_name": str, "post_ids": list[int]}.
    """
    if not posts:
        return []

    lang_config = get_language_config(content_language)

    # Build posts list for prompt — include tags if available
    posts_text = []
    for post in posts:
        desc = post.description or truncate(post.text, 80)
        tags = tags_map.get(post.message_id, []) if tags_map else []
        tags_str = f" [{', '.join(tags)}]" if tags else ""
        posts_text.append(f"[{post.message_id}] {desc}{tags_str}")

    prompt = TOC_GROUPING_PROMPT.format(
        groups_count=TOC_GROUPS_COUNT,
        language=lang_config["name"],
        posts="\n".join(posts_text),
    )

    try:
        c = _get_client()
        response = await asyncio.wait_for(
            asyncio.to_thread(
                c.models.generate_content,
                model=GEMINI_MODEL,
                contents=prompt,
            ),
            timeout=180,
        )
        return _parse_grouping_response(response.text)
    except asyncio.TimeoutError:
        logger.error("TOC grouping timeout")
        return _fallback_grouping(posts, content_language)
    except Exception as e:
        logger.error("TOC grouping error: %s", e)
        return _fallback_grouping(posts, content_language)


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
        groups.append(
            {
                "group_name": item["group_name"],
                "post_ids": [int(pid) for pid in item["post_ids"]],
            }
        )
    return groups


def _fallback_grouping(posts: list[Post], content_language: str = "en") -> list[dict]:
    """Simple fallback: split posts into groups by chronological order."""
    lang_config = get_language_config(content_language)
    fallback_name = lang_config["fallback_group"]
    chunk_size = max(1, len(posts) // TOC_GROUPS_COUNT)
    groups = []
    sorted_posts = sorted(posts, key=lambda p: p.score, reverse=True)
    for i in range(TOC_GROUPS_COUNT):
        chunk = sorted_posts[i * chunk_size : (i + 1) * chunk_size]
        if chunk:
            groups.append(
                {
                    "group_name": f"{fallback_name} {i + 1}",
                    "post_ids": [p.message_id for p in chunk],
                }
            )
    return groups


def _build_toc_html(
    channel: Channel,
    groups: list[dict],
    post_map: dict[int, Post],
    lang: str = "ru",
    desc_overrides: dict[int, str] | None = None,
    group_name_overrides: list[str] | None = None,
) -> str:
    """Build TOC HTML from groups and post data.

    Args:
        channel: Channel object.
        groups: List of {"group_name": str, "post_ids": list[int]}.
        post_map: {message_id: Post} lookup.
        lang: Language for static text.
        desc_overrides: {message_id: translated_description} overrides.
        group_name_overrides: Translated group names (same order as groups).
    """
    msg = get_messages(lang)
    date_str = datetime.now(timezone.utc).strftime("%d.%m.%Y")
    header = f"<b>{msg.TOC_HEADER.format(username=channel.username)}</b>\n{msg.TOC_UPDATED.format(date=date_str)}\n"

    sections = []
    chars_used = len(header)
    used_post_ids = set()

    for i, group in enumerate(groups):
        emoji = GROUP_EMOJIS[i % len(GROUP_EMOJIS)]
        group_name = group_name_overrides[i] if group_name_overrides else group["group_name"]

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
            # Use translated description if available
            if desc_overrides and post.message_id in desc_overrides:
                desc = truncate(desc_overrides[post.message_id], 50)
            else:
                desc = truncate(post.description or post.text, 50)
            desc = desc.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            line = f'{j}. <a href="{post.post_url}">{desc}</a>'
            post_lines.append(line)

        blockquote_content = "\n".join(post_lines)
        section = (
            f"\n<b>{emoji} {group_name}</b> ({total_in_group})\n"
            f"<blockquote expandable>{blockquote_content}</blockquote>"
        )

        # Check if we exceed limit
        if chars_used + len(section) > TOC_MAX_LENGTH:
            for trim in range(len(post_lines) - 1, 2, -1):
                trimmed = "\n".join(post_lines[:trim])
                section = (
                    f"\n<b>{emoji} {group_name}</b> ({total_in_group})\n<blockquote expandable>{trimmed}</blockquote>"
                )
                if chars_used + len(section) <= TOC_MAX_LENGTH:
                    break
            else:
                break

        sections.append(section)
        chars_used += len(section)

    toc = header + "".join(sections)

    if len(toc) > TOC_MAX_LENGTH:
        toc = toc[: TOC_MAX_LENGTH - 1] + "…"

    return toc


async def generate_compact_toc(
    channel: Channel, queries, content_language: str = "en"
) -> tuple[str, list[dict], dict[int, Post]]:
    """Generate compact TOC with expandable blockquotes.

    Returns (toc_html, groups, post_map) so translated versions can reuse the structure.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=TOC_POSTS_PERIOD_DAYS)
    all_posts = queries.get_posts_since(channel.id, cutoff.isoformat())

    if not all_posts:
        msg = get_messages(content_language)
        return f"{msg.TOC_HEADER.format(username=channel.username)}\n\n{msg.TOC_NO_POSTS}", [], {}

    tags_map = queries.get_tags_for_posts(channel.id)
    groups = await generate_toc_groups(all_posts, tags_map, content_language)
    if not groups:
        msg = get_messages(content_language)
        return f"{msg.TOC_HEADER.format(username=channel.username)}\n\n{msg.TOC_NO_POSTS}", [], {}

    post_map = {p.message_id: p for p in all_posts}
    toc = _build_toc_html(channel, groups, post_map, lang=content_language)

    return toc, groups, post_map


async def generate_translated_toc(
    channel: Channel,
    groups: list[dict],
    post_map: dict[int, Post],
    queries,
    lang: str = "en",
) -> str | None:
    """Build TOC in target language from translated parts.

    Uses already-translated post descriptions from DB and translates group names.
    Returns translated TOC HTML, or None on failure.
    """
    if not groups:
        msg = get_messages(lang)
        return f"{msg.TOC_HEADER.format(username=channel.username)}\n\n{msg.TOC_NO_POSTS}"

    from src.services.translator import translate_texts

    # 1. Get translated descriptions for posts in TOC
    post_ids = [p.id for p in post_map.values()]
    desc_translations_by_id = queries.get_post_translations(post_ids, lang)

    # Convert from post.id -> post.message_id keying for _build_toc_html
    id_to_msg_id = {p.id: p.message_id for p in post_map.values()}
    desc_overrides = {}
    for pid, desc in desc_translations_by_id.items():
        if pid in id_to_msg_id:
            desc_overrides[id_to_msg_id[pid]] = desc

    # 2. Translate group names
    group_names = [g["group_name"] for g in groups]
    try:
        group_names_translated = await translate_texts(group_names, target_lang=lang)
    except Exception as e:
        logger.error("Failed to translate TOC group names: %s", e)
        group_names_translated = group_names

    # 3. Build TOC HTML with translated parts
    return _build_toc_html(
        channel,
        groups,
        post_map,
        lang=lang,
        desc_overrides=desc_overrides,
        group_name_overrides=group_names_translated,
    )


def should_update_pinned(channel: Channel, new_toc: str) -> bool:
    """Check if pinned post needs updating."""
    if not channel.pinned_message_id or not channel.pinned_chat_id:
        return False
    new_hash = content_hash(new_toc)
    return new_hash != channel.pinned_content_hash
