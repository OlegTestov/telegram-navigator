"""Hourly scheduler: fetch, classify, score, update TOC."""

import asyncio
import logging
import sys

from telegram import Bot

from src.config.settings import TELEGRAM_BOT_TOKEN, validate_config
from src.database.factory import create_queries
from src.services.fetcher import create_telethon_client, fetch_channel_posts
from src.services.classifier import classify_posts, generate_topic_summary
from src.services.toc_generator import generate_compact_toc, should_update_pinned
from src.utils.helpers import content_hash

logger = logging.getLogger(__name__)


async def process_channel(channel, queries: DatabaseQueries, bot: Bot):
    """Process a single channel: fetch → classify → score → update TOC."""
    logger.info("Processing @%s (last_msg_id=%d)", channel.username, channel.last_fetched_message_id)

    # 1. Fetch new posts
    client = create_telethon_client()
    async with client:
        title, raw_posts = await fetch_channel_posts(
            client, channel.username, channel.last_fetched_message_id
        )

    if title and title != channel.title:
        queries.update_channel_title(channel.id, title)

    # 2. Upsert posts
    if raw_posts:
        new_count = queries.upsert_posts(channel.id, raw_posts)
        logger.info("Upserted %d posts for @%s", new_count, channel.username)

        # Update sync state with highest message_id
        max_msg_id = max(p["message_id"] for p in raw_posts)
        if max_msg_id > channel.last_fetched_message_id:
            total = queries.get_channel_post_count(channel.id)
            queries.update_channel_sync(channel.id, max_msg_id, total)

    # 3. Classify unclassified posts
    unclassified = queries.get_unclassified_posts(channel.id)
    if unclassified:
        logger.info("Classifying %d posts for @%s", len(unclassified), channel.username)

        existing_topics = [t.name for t in queries.get_topics(channel.id)]
        post_dicts = [{"text": p.text} for p in unclassified]
        classifications = await classify_posts(post_dicts, existing_topics)

        for cls_result in classifications:
            idx = cls_result["post_index"]
            if idx >= len(unclassified):
                continue
            post = unclassified[idx]

            # Save classification
            queries.set_post_classification(
                post.id, cls_result["description"], cls_result["usefulness"]
            )

            # Link topics
            for topic_name in cls_result["topics"]:
                topic = queries.get_or_create_topic(channel.id, topic_name.strip())
                queries.link_post_topic(post.id, topic.id)

    # 4. Recalculate scores
    queries.recalculate_scores(channel.id)

    # 5. Update topic counts
    queries.update_topic_counts(channel.id)

    # 6. Generate topic summaries for topics without one
    topics = queries.get_topics(channel.id)
    for topic in topics:
        if not topic.summary and topic.post_count > 0:
            top_posts = queries.get_top_posts_by_topic(topic.id, limit=15)
            descriptions = [p.description for p in top_posts if p.description]
            if descriptions:
                summary = await generate_topic_summary(topic.name, descriptions)
                if summary:
                    queries.update_topic_summary(topic.id, summary)

    # 7. Update pinned post if configured
    channel = queries.get_channel_by_id(channel.id)  # Refresh
    toc = generate_compact_toc(channel, queries)
    if should_update_pinned(channel, toc):
        try:
            await bot.edit_message_text(
                chat_id=channel.pinned_chat_id,
                message_id=channel.pinned_message_id,
                text=toc,
                parse_mode=None,  # plain text, links are plain URLs
            )
            queries.update_pinned_hash(channel.id, content_hash(toc))
            logger.info("Updated pinned post for @%s", channel.username)
        except Exception as e:
            logger.error("Failed to update pinned for @%s: %s", channel.username, e)

    logger.info("Done processing @%s", channel.username)


async def run_scheduler():
    """Main scheduler loop: process all active channels."""
    validate_config()

    queries = create_queries()
    bot = Bot(token=TELEGRAM_BOT_TOKEN)

    channels = queries.get_active_channels()
    if not channels:
        logger.info("No active channels to process.")
        return

    logger.info("Processing %d active channel(s)...", len(channels))

    for channel in channels:
        try:
            await process_channel(channel, queries, bot)
        except Exception as e:
            logger.error("Error processing @%s: %s", channel.username, e, exc_info=True)

    logger.info("Scheduler run complete.")


def main():
    logger.info("=" * 40)
    logger.info("Starting content-table scheduler...")
    logger.info("=" * 40)

    try:
        asyncio.run(run_scheduler())
    except Exception as e:
        logger.critical("Scheduler failed: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
