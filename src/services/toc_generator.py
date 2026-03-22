"""Generate compact Table of Contents for a channel."""

import logging
from datetime import datetime, timezone

from src.database.queries import DatabaseQueries
from src.database.models import Channel
from src.config.constants import TOC_TARGET_LENGTH, TOC_MAX_LENGTH
from src.utils.helpers import content_hash, truncate

logger = logging.getLogger(__name__)


def generate_compact_toc(
    channel: Channel,
    queries: DatabaseQueries,
) -> str:
    """Generate compact TOC string (1000-2000 chars).

    Selects top posts per topic, fitting within char budget.
    """
    topics = queries.get_topics(channel.id)
    if not topics:
        return f"📚 Оглавление @{channel.username}\n\nПока нет проиндексированных постов."

    date_str = datetime.now(timezone.utc).strftime("%d.%m.%Y")
    header = f"📚 Оглавление @{channel.username}\nОбновлено: {date_str}\n"

    # Calculate how many posts per topic based on budget
    # header ~60 chars, each topic line ~20 chars, each post ~70 chars
    remaining = TOC_MAX_LENGTH - len(header) - 20  # safety margin
    topic_header_cost = 25  # "🔹 Тема (N)\n"
    post_line_cost = 75  # "• description → link\n"

    # Distribute posts across topics proportionally to post_count
    total_posts_budget = (remaining - len(topics) * topic_header_cost) // post_line_cost
    total_posts_budget = max(total_posts_budget, len(topics))  # at least 1 per topic

    total_topic_posts = sum(t.post_count for t in topics)
    if total_topic_posts == 0:
        total_topic_posts = 1

    sections = []
    chars_used = len(header)

    for topic in topics:
        if topic.post_count == 0:
            continue

        # Proportional allocation, minimum 1
        alloc = max(1, round(total_posts_budget * topic.post_count / total_topic_posts))
        alloc = min(alloc, 4)  # max 4 posts per topic

        top_posts = queries.get_top_posts_by_topic(topic.id, limit=alloc)
        if not top_posts:
            continue

        emoji = topic.emoji or "📌"
        topic_line = f"\n{emoji} {topic.name} ({topic.post_count})"

        post_lines = []
        for post in top_posts:
            desc = post.description or truncate(post.text, 50)
            line = f"• {desc} → {post.post_url}"
            post_lines.append(line)

        section = topic_line + "\n" + "\n".join(post_lines)
        section_len = len(section)

        if chars_used + section_len > TOC_MAX_LENGTH:
            # Try with fewer posts
            if len(post_lines) > 1:
                section = topic_line + "\n" + post_lines[0]
                section_len = len(section)
            if chars_used + section_len > TOC_MAX_LENGTH:
                break

        sections.append(section)
        chars_used += section_len

    toc = header + "".join(sections)

    # If still too long, truncate last section
    if len(toc) > TOC_MAX_LENGTH:
        toc = toc[:TOC_MAX_LENGTH - 1] + "…"

    return toc


def should_update_pinned(channel: Channel, new_toc: str) -> bool:
    """Check if pinned post needs updating."""
    if not channel.pinned_message_id or not channel.pinned_chat_id:
        return False
    new_hash = content_hash(new_toc)
    return new_hash != channel.pinned_content_hash
