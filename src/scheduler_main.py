"""Hourly scheduler: fetch, classify, score, update TOC, digest, translate."""

import asyncio
import logging
import sys

from telegram import Bot
from telethon.errors import FloodWaitError

from src.config.constants import FETCH_DELAY_SECONDS
from src.config.settings import (
    BATCH_SIZE,
    DB_BACKEND,
    EMBEDDINGS_ENABLED,
    TELEGRAM_BOT_TOKEN,
    get_setting,
    get_translation_languages,
    validate_config,
)
from src.database.factory import create_queries
from src.services.classifier import classify_posts, generate_topic_summary
from src.services.digest import run_digest_cycle, should_run_digest
from src.services.fetcher import create_telethon_client, fetch_channel_posts
from src.services.toc_generator import generate_compact_toc, generate_translated_toc, should_update_pinned
from src.services.translator import translate_texts
from src.utils.helpers import content_hash

if EMBEDDINGS_ENABLED:
    from src.services.embedder import generate_embeddings, serialize_float32

logger = logging.getLogger(__name__)


async def process_channel(channel, queries, bot, client, content_language: str):
    """Process a single channel: fetch → classify → score → update TOC. No translation."""
    logger.info("Processing @%s (last_msg_id=%d)", channel.username, channel.last_fetched_message_id)

    # 1. Fetch new posts
    title, raw_posts, peer_id, access_hash = await fetch_channel_posts(
        client,
        channel.username,
        channel.last_fetched_message_id,
        peer_id=channel.peer_id,
        access_hash=channel.access_hash,
    )

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

        max_msg_id = max(p["message_id"] for p in raw_posts)
        if max_msg_id > channel.last_fetched_message_id:
            total = queries.get_channel_post_count(channel.id)
            queries.update_channel_sync(channel.id, max_msg_id, total)

    # 3. Classify unclassified posts
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
        classifications = await classify_posts(post_dicts, existing_topics, content_language)

        post_by_idx = {i: p for i, p in enumerate(unclassified)}
        classified_count = 0

        for cls_result in classifications:
            idx = cls_result["post_index"]
            if idx not in post_by_idx:
                continue
            post = post_by_idx[idx]

            queries.set_post_classification(post.id, cls_result["description"], cls_result["usefulness"])

            for topic_name in cls_result["topics"]:
                topic = queries.get_or_create_topic(channel.id, topic_name.strip())
                queries.link_post_topic(post.id, topic.id)

            del post_by_idx[idx]
            classified_count += 1

        logger.info("Classified %d/%d in this batch", classified_count, len(unclassified))
        has_changes = True

    # 4. Generate embeddings
    if EMBEDDINGS_ENABLED and hasattr(queries, "get_posts_without_embeddings"):
        try:
            unembedded = queries.get_posts_without_embeddings(channel.id, limit=500)
            while unembedded:
                logger.info("Generating embeddings for %d posts in @%s", len(unembedded), channel.username)
                texts = [f"{p.description or ''} {p.text[:500]}".strip() for p in unembedded]
                embeddings = await generate_embeddings(texts)
                if embeddings and len(embeddings) == len(unembedded):
                    if DB_BACKEND == "supabase":
                        pairs = [(post.id, emb) for post, emb in zip(unembedded, embeddings)]
                    else:
                        pairs = [(post.id, serialize_float32(emb)) for post, emb in zip(unembedded, embeddings)]
                    queries.upsert_embeddings(pairs)
                    logger.info("Stored %d embeddings for @%s", len(pairs), channel.username)
                else:
                    logger.warning("Embedding generation failed or count mismatch, skipping")
                    break
                unembedded = queries.get_posts_without_embeddings(channel.id, limit=500)
        except Exception as e:
            logger.error("Embedding error for @%s: %s", channel.username, e)

    if not has_changes:
        logger.info("No changes for @%s, skipping heavy operations", channel.username)
        return

    # 5. Recalculate scores
    queries.recalculate_scores(channel.id)

    # 6. Update topic counts
    queries.update_topic_counts(channel.id)

    # 7. Generate topic summaries
    topics = queries.get_topics(channel.id)
    for topic in topics:
        if not topic.summary and topic.post_count > 0:
            top_posts = queries.get_top_posts_by_topic(topic.id, limit=15)
            descriptions = [p.description for p in top_posts if p.description]
            if descriptions:
                summary = await generate_topic_summary(topic.name, descriptions, content_language)
                if summary:
                    queries.update_topic_summary(topic.id, summary)

    # 8. Generate TOC
    channel = queries.get_channel_by_id(channel.id)  # Refresh
    toc, groups, post_map = await generate_compact_toc(channel, queries, content_language)
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


async def translate_channel_priority(channel, queries, trans_langs: list[str], content_language: str = "en"):
    """Translate high-priority content: topic names, summaries, TOC."""
    for lang in trans_langs:
        # 1. Translate topic names and summaries
        topics = queries.get_topics(channel.id)
        if topics:
            existing_tr = queries.get_topic_translations([t.id for t in topics], lang)
            untranslated = [t for t in topics if t.id not in existing_tr]
            if untranslated:
                names = [t.name for t in untranslated]
                names_tr = await translate_texts(names, target_lang=lang)

                # Batch-translate summaries (avoid N+1 Gemini calls)
                summaries = [t.summary or "" for t in untranslated]
                summaries_tr = await translate_texts(summaries, target_lang=lang)

                saved = 0
                for topic, name_tr, summary_tr in zip(untranslated, names_tr, summaries_tr):
                    # Skip if translation failed (returned original text)
                    if name_tr == topic.name:
                        continue
                    final_summary = summary_tr if topic.summary and summary_tr and summary_tr != topic.summary else None
                    queries.save_topic_translation(topic.id, lang, name=name_tr, summary=final_summary)
                    saved += 1
                logger.info("Translated %d/%d topics for @%s to %s", saved, len(untranslated), channel.username, lang)

            # Translate summaries for topics that have name translation but missing summary
            needs_summary = [
                t for t in topics
                if t.id in existing_tr
                and t.summary
                and not (existing_tr[t.id].get("summary") if isinstance(existing_tr[t.id], dict) else None)
            ]
            if needs_summary:
                summaries = [t.summary for t in needs_summary]
                summaries_tr = await translate_texts(summaries, target_lang=lang)
                updated = 0
                for topic, summary_tr in zip(needs_summary, summaries_tr):
                    if summary_tr and summary_tr != topic.summary:
                        existing_name = existing_tr[topic.id]
                        name = existing_name.get("name") if isinstance(existing_name, dict) else existing_name
                        queries.save_topic_translation(topic.id, lang, name=name, summary=summary_tr)
                        updated += 1
                if updated:
                    logger.info("Updated %d topic summaries for @%s to %s", updated, channel.username, lang)

        # 2. Translate TOC
        if channel.cached_toc:
            channel_refreshed = queries.get_channel_by_id(channel.id)
            toc_existing = queries.get_toc_translation(channel.id, lang)
            # Regenerate if no translation exists (will be rebuilt from translated parts)
            if not toc_existing or not toc_existing.strip():
                from src.services.toc_generator import generate_compact_toc

                _, groups, post_map = await generate_compact_toc(channel_refreshed, queries, content_language)
                if groups:
                    toc_tr = await generate_translated_toc(channel_refreshed, groups, post_map, queries, lang=lang)
                    if toc_tr:
                        queries.save_toc_translation(channel.id, lang, toc_tr)
                        logger.info("Translated TOC for @%s to %s", channel.username, lang)


async def translate_post_descriptions(channel, queries, trans_langs: list[str], batch_size: int = 50):
    """Translate post descriptions (low priority, batched)."""
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(days=365)
    all_posts = queries.get_posts_since(channel.id, cutoff.isoformat())
    posts_with_desc = [p for p in all_posts if p.description]

    if not posts_with_desc:
        return

    for lang in trans_langs:
        existing = queries.get_post_translations([p.id for p in posts_with_desc], lang)
        untranslated = [p for p in posts_with_desc if p.id not in existing]

        if not untranslated:
            continue

        logger.info("Translating %d post descriptions for @%s to %s", len(untranslated), channel.username, lang)

        for i in range(0, len(untranslated), batch_size):
            batch = untranslated[i : i + batch_size]
            descriptions = [p.description for p in batch]
            descriptions_tr = await translate_texts(descriptions, target_lang=lang)
            translations = [
                (p.id, lang, desc_tr)
                for p, desc_tr in zip(batch, descriptions_tr)
                if desc_tr and desc_tr != p.description
            ]
            if translations:
                queries.save_post_translations(translations)
            logger.info("  Translated batch %d-%d (%d saved)", i, i + len(batch), len(translations))


async def run_scheduler():
    """Main scheduler: index → digest → translate priority → translate descriptions."""
    validate_config()

    queries = create_queries()
    bot = Bot(token=TELEGRAM_BOT_TOKEN)

    # Read settings from DB (with .env fallback)
    content_language = get_setting(queries, "content_language")
    trans_langs = get_translation_languages(queries)
    logger.info("Content language: %s, Translation languages: %s", content_language, trans_langs or "disabled")

    channels = queries.get_active_channels()
    if not channels:
        logger.info("No active channels to process.")
        return

    logger.info("Processing %d active channel(s)...", len(channels))

    # === Phase 1: Index all channels (fast, no translation) ===
    client = create_telethon_client()
    async with client:
        for i, channel in enumerate(channels):
            try:
                await process_channel(channel, queries, bot, client, content_language)
            except FloodWaitError as e:
                logger.warning(
                    "FloodWait for %d seconds while processing @%s, sleeping...",
                    e.seconds,
                    channel.username,
                )
                await asyncio.sleep(e.seconds + 5)
                try:
                    await process_channel(channel, queries, bot, client, content_language)
                except Exception as retry_err:
                    logger.error("Retry failed for @%s: %s", channel.username, retry_err, exc_info=True)
            except Exception as e:
                logger.error("Error processing @%s: %s", channel.username, e, exc_info=True)

            if i < len(channels) - 1:
                await asyncio.sleep(FETCH_DELAY_SECONDS)

    # === Phase 2: Digests (inline translation for subscribers) ===
    try:
        if should_run_digest(queries):
            logger.info("Running digest cycle...")
            await run_digest_cycle(queries, bot, content_language, trans_langs or None)
            logger.info("Digest cycle complete.")
        else:
            logger.info("Skipping digest (not time yet)")
    except Exception as e:
        logger.error("Digest cycle failed: %s", e, exc_info=True)

    # === Phase 3: Translate high-priority content (TOC, topics, summaries) ===
    if trans_langs:
        logger.info("Translating high-priority content...")
        channels = queries.get_active_channels()  # Refresh
        for channel in channels:
            try:
                await translate_channel_priority(channel, queries, trans_langs, content_language)
            except Exception as e:
                logger.error("Priority translation failed for @%s: %s", channel.username, e)

    # === Phase 4: Translate post descriptions (low priority) ===
    if trans_langs:
        logger.info("Translating post descriptions...")
        for channel in channels:
            try:
                await translate_post_descriptions(channel, queries, trans_langs)
            except Exception as e:
                logger.error("Description translation failed for @%s: %s", channel.username, e)

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
