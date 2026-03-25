"""Channel digest generation and delivery to subscribers."""

import asyncio
import html
import logging
import re
from datetime import datetime, timedelta, timezone

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from src.bot import messages as msg
from src.config.constants import (
    DIGEST_INTERVAL_HOURS,
    DIGEST_MAX_POSTS_PER_CHANNEL,
    DIGEST_MAX_POST_TEXT,
    DIGEST_MESSAGE_MAX_LENGTH,
)
from src.config.settings import GEMINI_MODEL

logger = logging.getLogger(__name__)


def should_run_digest(queries) -> bool:
    """Check if enough time passed since last digest (DB-based, not clock-based)."""
    latest = queries.get_latest_digest_period_end()
    if not latest:
        return True
    latest_dt = datetime.fromisoformat(latest.replace("Z", "+00:00"))
    if latest_dt.tzinfo is None:
        latest_dt = latest_dt.replace(tzinfo=timezone.utc)
    elapsed = datetime.now(timezone.utc) - latest_dt
    return elapsed >= timedelta(hours=DIGEST_INTERVAL_HOURS)


async def summarize_posts_for_digest(posts: list) -> list[str]:
    """Summarize posts via Gemini in one batch call. Returns list of summary strings."""
    from src.services.classifier import _get_client

    posts_text = []
    for i, post in enumerate(posts, 1):
        text = (post.text or "")[:DIGEST_MAX_POST_TEXT]
        posts_text.append(f"Post {i}:\n{text}")

    prompt = (
        f"Summarize each of the following Telegram channel posts in 1-2 sentences, "
        f"extracting the most important and key information. "
        f"Respond in Russian.\n"
        f"Return exactly {len(posts)} summaries as a numbered list (1. ... 2. ... etc).\n\n"
        + "\n\n".join(posts_text)
    )

    try:
        client = _get_client()
        response = await asyncio.to_thread(
            client.models.generate_content, model=GEMINI_MODEL, contents=prompt,
        )
        summaries = _parse_numbered_list(response.text, len(posts))
    except Exception as e:
        logger.error("Gemini summarization failed: %s", e)
        # Fallback: use description or truncated text
        summaries = [
            p.description or (p.text[:200] + "..." if len(p.text) > 200 else p.text)
            for p in posts
        ]

    # Ensure we have exactly len(posts) summaries
    while len(summaries) < len(posts):
        p = posts[len(summaries)]
        summaries.append(p.description or p.text[:200])

    return summaries


def _parse_numbered_list(text: str, expected_count: int) -> list[str]:
    """Parse a numbered list response from Gemini."""
    lines = re.findall(r"^\d+\.\s*(.+)", text, re.MULTILINE)
    if lines:
        return lines
    # Fallback: split by newlines
    lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
    return lines


async def generate_channel_digest_content(channel, posts, total_count: int = None) -> str:
    """Format a single channel's digest block as HTML with Gemini summaries."""
    total = total_count if total_count is not None else len(posts)
    capped = posts[:DIGEST_MAX_POSTS_PER_CHANNEL]

    summaries = await summarize_posts_for_digest(capped)

    title = html.escape(channel.title or channel.username)
    lines = [f"<b>{title}:</b>"]
    for summary, post in zip(summaries, capped):
        safe_summary = html.escape(summary)
        lines.append(f'  • {safe_summary} (<a href="{post.post_url}">link</a>)')
    if total > DIGEST_MAX_POSTS_PER_CHANNEL:
        lines.append(msg.DIGEST_MORE_POSTS.format(count=total - DIGEST_MAX_POSTS_PER_CHANNEL))

    return "\n".join(lines)


def assemble_user_digest(
    channel_digests: list[tuple[dict, str]],
    period_start: datetime,
    period_end: datetime,
) -> list[str]:
    """Assemble per-user digest message(s), splitting at ~4000 chars."""
    fmt = "%H:%M"
    date_fmt = "%d.%m.%Y"
    period_str = (
        f"{period_start.strftime(fmt)} — {period_end.strftime(fmt)}, "
        f"{period_end.strftime(date_fmt)}"
    )
    header = msg.DIGEST_HEADER.format(period=period_str)

    # Join all channel blocks with double newline
    sections = [content for _, content in channel_digests]
    full_text = header + "\n" + "\n\n".join(sections)

    return _split_message(full_text, DIGEST_MESSAGE_MAX_LENGTH)


def _split_message(text: str, max_length: int = 4000) -> list[str]:
    """Split a long message into chunks respecting section boundaries."""
    if len(text) <= max_length:
        return [text]

    chunks = []
    sections = text.split("\n\n")
    current = ""

    for section in sections:
        if len(section) > max_length:
            # Single section too long — split by lines
            if current:
                chunks.append(current.rstrip())
                current = ""
            for line in section.split("\n"):
                if len(current) + len(line) + 1 > max_length:
                    if current:
                        chunks.append(current.rstrip())
                    current = line + "\n"
                else:
                    current += line + "\n"
        elif len(current) + len(section) + 2 > max_length:
            if current:
                chunks.append(current.rstrip())
            current = section + "\n\n"
        else:
            current += section + "\n\n"

    if current.strip():
        chunks.append(current.rstrip())

    return chunks


async def run_digest_cycle(queries, bot: Bot):
    """Generate per-channel digests and deliver to subscribers."""
    now = datetime.now(timezone.utc)
    # Align to nearest past boundary (0, 6, 12, 18 UTC)
    aligned_hour = (now.hour // DIGEST_INTERVAL_HOURS) * DIGEST_INTERVAL_HOURS
    period_end = now.replace(hour=aligned_hour, minute=0, second=0, microsecond=0)
    period_start = period_end - timedelta(hours=DIGEST_INTERVAL_HOURS)

    period_start_iso = period_start.isoformat()
    period_end_iso = period_end.isoformat()

    channels = queries.get_active_channels()
    if not channels:
        return

    # 1. Generate per-channel digests
    generated_digests = []
    for channel in channels:
        total_count = queries.count_posts_for_digest(
            channel.id, period_start_iso, period_end_iso,
        )
        if total_count == 0:
            logger.info("No posts for @%s in digest period, skipping", channel.username)
            continue

        posts = queries.get_posts_for_digest(
            channel.id, period_start_iso, period_end_iso,
            limit=DIGEST_MAX_POSTS_PER_CHANNEL,
        )
        content = await generate_channel_digest_content(channel, posts, total_count)
        digest_id = queries.save_channel_digest(
            channel.id, period_start_iso, period_end_iso,
            content, total_count,
        )
        generated_digests.append({
            "id": digest_id,
            "channel_id": channel.id,
            "content": content,
            "channel": channel,
        })
        logger.info(
            "Generated digest for @%s: %d posts",
            channel.username, len(posts),
        )

    if not generated_digests:
        logger.info("No digests generated (no posts in any channel)")
        return

    # 2. Deliver to subscribers
    subscribers = queries.get_all_subscribers_with_channels()
    if not subscribers:
        logger.info("No subscribers, skipping delivery")
        return

    digest_by_channel = {d["channel_id"]: d for d in generated_digests}

    for user_id, channel_ids in subscribers.items():
        # Collect digests for this user's channels
        user_digests = []
        for cid in channel_ids:
            if cid in digest_by_channel:
                d = digest_by_channel[cid]
                user_digests.append((d, d["content"]))

        if not user_digests:
            continue

        # Check which digests haven't been delivered yet
        digest_ids = [d["id"] for d, _ in user_digests]
        undelivered_ids = queries.get_undelivered_digest_ids(user_id, digest_ids)
        if not undelivered_ids:
            continue

        undelivered_set = set(undelivered_ids)
        user_digests = [(d, c) for d, c in user_digests if d["id"] in undelivered_set]

        messages = assemble_user_digest(user_digests, period_start, period_end)

        menu_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Открыть меню", callback_data="open_menu")]
        ])
        try:
            for i, text in enumerate(messages):
                is_last = i == len(messages) - 1
                await bot.send_message(
                    chat_id=user_id,
                    text=text,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                    reply_markup=menu_kb if is_last else None,
                )
            # Record delivery
            for d, _ in user_digests:
                queries.record_digest_delivery(user_id, d["id"])
            logger.info("Delivered digest to user %d (%d channels)", user_id, len(user_digests))
        except Exception as e:
            error_msg = str(e).lower()
            # Auto-unsubscribe if user blocked bot or is unreachable
            if any(kw in error_msg for kw in ("forbidden", "blocked", "deactivated", "not found", "chat not found")):
                logger.warning("User %d unreachable (%s), removing all subscriptions", user_id, e)
                for cid in channel_ids:
                    queries.unsubscribe_user(user_id, cid)
            else:
                logger.error("Failed to deliver digest to user %d: %s", user_id, e)
            # Record delivery anyway to avoid retry loops
            for d, _ in user_digests:
                queries.record_digest_delivery(user_id, d["id"])
