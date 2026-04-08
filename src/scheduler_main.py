"""Hourly scheduler: fetch, classify, score, update TOC."""

import asyncio
import logging
import sys

from telegram import Bot
from telethon.errors import FloodWaitError

from src.config.constants import FETCH_DELAY_SECONDS
from src.config.settings import BATCH_SIZE, EMBEDDINGS_ENABLED, TELEGRAM_BOT_TOKEN, validate_config
from src.database.factory import create_queries
from src.services.classifier import classify_posts, generate_topic_summary
from src.services.digest import run_digest_cycle, should_run_digest
from src.services.fetcher import create_telethon_client, fetch_channel_posts
from src.services.toc_generator import generate_compact_toc, should_update_pinned
from src.utils.helpers import content_hash

if EMBEDDINGS_ENABLED:
    from src.services.embedder import generate_embeddings, serialize_float32

logger = logging.getLogger(__name__)


async def process_channel(channel, queries, bot, client):
    """Process a single channel: fetch → classify → score → update TOC."""
    logger.info("Processing @%s (last_msg_id=%d)", channel.username, channel.last_fetched_message_id)

    # 1. Fetch new posts (use peer_id + access_hash to avoid username resolution)
    title, raw_posts, peer_id, access_hash = await fetch_channel_posts(
        client,
        channel.username,
        channel.last_fetched_message_id,
        peer_id=channel.peer_id,
        access_hash=channel.access_hash,
    )

    # Save peer_id and access_hash for future fast resolution
    if peer_id and (peer_id != channel.peer_id or access_hash != channel.access_hash):
        queries.update_channel_peer_id(channel.id, peer_id, access_hash)

    if title and title != channel.title:
        queries.update_channel_title(channel.id, title)

    # 2. Upsert posts
    has_changes = False
    if raw_posts:
        new_count = queries.upsert_posts(channel.id, raw_posts)
        logger.info("Upserted %d posts for @%s", new_count, channel.username)
        has_changes = new_count > 0

        # Update sync state with highest message_id
        max_msg_id = max(p["message_id"] for p in raw_posts)
        if max_msg_id > channel.last_fetched_message_id:
            total = queries.get_channel_post_count(channel.id)
            queries.update_channel_sync(channel.id, max_msg_id, total)

    # 3. Classify unclassified posts — loop until all done
    while True:
        unclassified = queries.get_unclassified_posts(channel.id, limit=BATCH_SIZE)
        if not unclassified:
            break

        total_remaining = queries.get_unclassified_count(channel.id)
        logger.info(
            "Classifying batch of %d posts for @%s (%d remaining)",
            len(unclassified),
            channel.username,
            total_remaining,
        )

        existing_topics = [t.name for t in queries.get_topics(channel.id)]
        post_dicts = [{"text": p.text, "post_id": p.id} for p in unclassified]
        classifications = await classify_posts(post_dicts, existing_topics)

        # Build index map for reliable matching
        post_by_idx = {i: p for i, p in enumerate(unclassified)}
        classified_count = 0

        for cls_result in classifications:
            idx = cls_result["post_index"]
            if idx not in post_by_idx:
                continue
            post = post_by_idx[idx]

            # Save classification
            queries.set_post_classification(post.id, cls_result["description"], cls_result["usefulness"])

            # Link topics
            for topic_name in cls_result["topics"]:
                topic = queries.get_or_create_topic(channel.id, topic_name.strip())
                queries.link_post_topic(post.id, topic.id)

            del post_by_idx[idx]
            classified_count += 1

        logger.info("Classified %d/%d in this batch", classified_count, len(unclassified))
        has_changes = True

    # 4. Generate embeddings for posts without them (runs even without new posts)
    if EMBEDDINGS_ENABLED and hasattr(queries, "get_posts_without_embeddings"):
        unembedded = queries.get_posts_without_embeddings(channel.id, limit=500)
        while unembedded:
            logger.info("Generating embeddings for %d posts in @%s", len(unembedded), channel.username)
            texts = [f"{p.description or ''} {p.text[:500]}".strip() for p in unembedded]
            embeddings = await generate_embeddings(texts)
            if embeddings and len(embeddings) == len(unembedded):
                if hasattr(queries, "vector_search"):
                    # Supabase: raw list[float] for pgvector
                    pairs = [(post.id, emb) for post, emb in zip(unembedded, embeddings)]
                else:
                    # SQLite: binary format for sqlite-vec
                    pairs = [(post.id, serialize_float32(emb)) for post, emb in zip(unembedded, embeddings)]
                queries.upsert_embeddings(pairs)
                logger.info("Stored %d embeddings for @%s", len(pairs), channel.username)
            else:
                logger.warning("Embedding generation failed or count mismatch, skipping")
                break
            unembedded = queries.get_posts_without_embeddings(channel.id, limit=500)

    if not has_changes:
        logger.info("No changes for @%s, skipping heavy operations", channel.username)
        return

    # 5. Recalculate scores
    queries.recalculate_scores(channel.id)

    # 6. Update topic counts
    queries.update_topic_counts(channel.id)

    # 7. Generate topic summaries for topics without one
    topics = queries.get_topics(channel.id)
    for topic in topics:
        if not topic.summary and topic.post_count > 0:
            top_posts = queries.get_top_posts_by_topic(topic.id, limit=15)
            descriptions = [p.description for p in top_posts if p.description]
            if descriptions:
                summary = await generate_topic_summary(topic.name, descriptions)
                if summary:
                    queries.update_topic_summary(topic.id, summary)

    # 8. Generate TOC, cache it, and update pinned post if configured
    channel = queries.get_channel_by_id(channel.id)  # Refresh
    toc = await generate_compact_toc(channel, queries)
    queries.save_cached_toc(channel.id, toc)
    if should_update_pinned(channel, toc):
        try:
            await bot.edit_message_text(
                chat_id=channel.pinned_chat_id,
                message_id=channel.pinned_message_id,
                text=toc,
                parse_mode="HTML",
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

    # One Telethon client for the entire run
    client = create_telethon_client()
    async with client:
        for i, channel in enumerate(channels):
            try:
                await process_channel(channel, queries, bot, client)
            except FloodWaitError as e:
                logger.warning(
                    "FloodWait for %d seconds while processing @%s, sleeping...",
                    e.seconds,
                    channel.username,
                )
                await asyncio.sleep(e.seconds + 5)
                # Retry once after waiting
                try:
                    await process_channel(channel, queries, bot, client)
                except Exception as retry_err:
                    logger.error("Retry failed for @%s: %s", channel.username, retry_err, exc_info=True)
            except Exception as e:
                logger.error("Error processing @%s: %s", channel.username, e, exc_info=True)

            # Pause between channels
            if i < len(channels) - 1:
                await asyncio.sleep(FETCH_DELAY_SECONDS)

    # Digest cycle: generate per-channel digests and deliver to subscribers
    try:
        if should_run_digest(queries):
            logger.info("Running digest cycle...")
            await run_digest_cycle(queries, bot)
            logger.info("Digest cycle complete.")
        else:
            logger.info("Skipping digest (not time yet)")
    except Exception as e:
        logger.error("Digest cycle failed: %s", e, exc_info=True)

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
