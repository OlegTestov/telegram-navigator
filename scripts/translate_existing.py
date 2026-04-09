#!/usr/bin/env python3
"""Translate existing content to configured translation languages.

Run once after deploying translation tables to populate translations
for all existing post descriptions, topic names, topic summaries, and TOCs.

Usage:
    python -m scripts.translate_existing
"""

import asyncio
import logging
import sys

from src.config.settings import get_translation_languages, validate_config
from src.database.factory import create_queries
from src.services.translator import translate_texts

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BATCH_SIZE = 50


async def translate_post_descriptions(queries, langs: list[str]):
    """Translate all post descriptions that don't have translations."""
    channels = queries.get_active_channels()
    total = 0

    for channel in channels:
        # Get ALL posts with descriptions (no date limit)
        all_posts_result = (
            queries.db.execute(
                lambda cid=channel.id: (
                    queries.db.client.table("ct_posts")
                    .select("id, description")
                    .eq("channel_id", cid)
                    .not_.is_("description", "null")
                    .execute()
                )
            )
            if hasattr(queries, "db")
            else None
        )

        if all_posts_result:
            posts_data = all_posts_result.data
        else:
            # SQLite fallback
            rows = queries.conn.execute(
                "SELECT id, description FROM ct_posts WHERE channel_id = ? AND description IS NOT NULL",
                (channel.id,),
            ).fetchall()
            posts_data = [{"id": r["id"], "description": r["description"]} for r in rows]

        if not posts_data:
            continue

        for lang in langs:
            # Filter out already translated
            post_ids = [p["id"] for p in posts_data]
            # Batch the ID lookup to avoid URL length limits
            existing = {}
            for i in range(0, len(post_ids), 500):
                batch_ids = post_ids[i : i + 500]
                existing.update(queries.get_post_translations(batch_ids, lang))

            untranslated = [p for p in posts_data if p["id"] not in existing]

            if not untranslated:
                logger.info(
                    "@%s: all %d descriptions already translated to %s", channel.username, len(posts_data), lang
                )
                continue

            logger.info(
                "@%s: translating %d/%d descriptions to %s...",
                channel.username,
                len(untranslated),
                len(posts_data),
                lang,
            )

            for i in range(0, len(untranslated), BATCH_SIZE):
                batch = untranslated[i : i + BATCH_SIZE]
                descriptions = [p["description"] for p in batch]
                descriptions_tr = await translate_texts(descriptions, target_lang=lang)

                translations = [
                    (p["id"], lang, desc_tr)
                    for p, desc_tr in zip(batch, descriptions_tr)
                    if desc_tr and desc_tr != p["description"]
                ]
                if translations:
                    queries.save_post_translations(translations)
                    total += len(translations)
                logger.info(
                    "  @%s [%s] batch %d-%d (%d saved)",
                    channel.username,
                    lang,
                    i,
                    i + len(batch),
                    len(translations),
                )

    logger.info("Total post descriptions translated: %d", total)


async def translate_topics(queries, langs: list[str]):
    """Translate all topic names and summaries."""
    channels = queries.get_active_channels()
    total = 0

    for channel in channels:
        topics = queries.get_topics(channel.id)
        if not topics:
            continue

        for lang in langs:
            existing = queries.get_topic_translations([t.id for t in topics], lang)
            untranslated = [t for t in topics if t.id not in existing]

            if not untranslated:
                logger.info("@%s: all %d topics already translated to %s", channel.username, len(topics), lang)
                continue

            logger.info(
                "@%s: translating %d/%d topics to %s...", channel.username, len(untranslated), len(topics), lang
            )

            names = [t.name for t in untranslated]
            names_tr = await translate_texts(names, target_lang=lang)

            summaries = [t.summary or "" for t in untranslated]
            summaries_tr = await translate_texts(summaries, target_lang=lang)

            for topic, name_tr, summary_tr in zip(untranslated, names_tr, summaries_tr):
                queries.save_topic_translation(
                    topic.id,
                    lang,
                    name=name_tr or topic.name,
                    summary=summary_tr if summary_tr and topic.summary else None,
                )
                total += 1

    logger.info("Total topics translated: %d", total)


async def regenerate_toc_translations(queries, langs: list[str]):
    """Regenerate translated TOC for all channels."""
    from src.config.settings import get_setting
    from src.services.toc_generator import generate_compact_toc, generate_translated_toc

    content_language = get_setting(queries, "content_language")
    channels = queries.get_active_channels()

    for channel in channels:
        if not channel.cached_toc:
            logger.info("@%s: no TOC, skipping", channel.username)
            continue

        _, groups, post_map = await generate_compact_toc(channel, queries, content_language)
        if not groups:
            logger.info("@%s: TOC grouping failed, skipping", channel.username)
            continue

        for lang in langs:
            logger.info("@%s: generating %s TOC...", channel.username, lang)
            toc_tr = await generate_translated_toc(channel, groups, post_map, queries, lang=lang)
            if toc_tr:
                queries.save_toc_translation(channel.id, lang, toc_tr)
                logger.info("@%s: %s TOC saved", channel.username, lang)
            else:
                logger.warning("@%s: %s TOC generation returned None", channel.username, lang)


async def main():
    validate_config()
    queries = create_queries()
    langs = get_translation_languages(queries)

    if not langs:
        logger.info("No translation languages configured. Nothing to do.")
        return

    logger.info("=== Translating existing content to: %s ===", ", ".join(langs))

    logger.info("\n--- Step 1: Post descriptions ---")
    await translate_post_descriptions(queries, langs)

    logger.info("\n--- Step 2: Topic names and summaries ---")
    await translate_topics(queries, langs)

    logger.info("\n--- Step 3: TOC regeneration ---")
    await regenerate_toc_translations(queries, langs)

    logger.info("\n=== Translation complete ===")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted.")
        sys.exit(0)
    except Exception as e:
        logger.critical("Failed: %s", e, exc_info=True)
        sys.exit(1)
