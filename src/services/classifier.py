"""Classify posts using Google Gemini."""

import asyncio
import json
import logging
from google import genai

from src.config.settings import GEMINI_API_KEY, GEMINI_MODEL, BATCH_SIZE
from src.config.prompts import CLASSIFICATION_PROMPT, TOPIC_SUMMARY_PROMPT
from src.config.constants import MAX_POST_TEXT_FOR_LLM
from src.utils.errors import ClassificationError

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


async def classify_posts(
    posts: list[dict],
    existing_topics: list[str],
) -> list[dict]:
    """Classify a list of posts into topics.

    Args:
        posts: List of dicts with 'text' and post index.
        existing_topics: List of existing topic names for the channel.

    Returns:
        List of dicts with 'post_index', 'topics', 'description', 'usefulness'.
    """
    if not posts:
        return []

    all_results = []

    for i in range(0, len(posts), BATCH_SIZE):
        batch = posts[i : i + BATCH_SIZE]
        batch_results = await _classify_batch(batch, existing_topics)
        all_results.extend(batch_results)

    return all_results


async def _classify_batch(
    posts: list[dict],
    existing_topics: list[str],
) -> list[dict]:
    """Classify a single batch of posts."""
    posts_text = []
    for idx, post in enumerate(posts):
        text = post["text"][:MAX_POST_TEXT_FOR_LLM]
        post_id = post.get("post_id", idx)
        posts_text.append(f"[Post {idx}, id={post_id}]\n{text}")

    topics_str = ", ".join(existing_topics) if existing_topics else "(пока нет тем)"

    prompt = CLASSIFICATION_PROMPT.format(
        existing_topics=topics_str,
        posts="\n\n".join(posts_text),
    )

    try:
        c = _get_client()
        response = await asyncio.wait_for(
            asyncio.to_thread(
                c.models.generate_content,
                model=GEMINI_MODEL,
                contents=prompt,
            ),
            timeout=60,
        )
        return _parse_classification_response(response.text, len(posts))
    except asyncio.TimeoutError:
        logger.error("Gemini classification timeout for batch of %d posts", len(posts))
    except Exception as e:
        logger.error("Gemini classification error: %s", e)
    # Fallback: return "Прочее" for all posts
    return [
        {
            "post_index": idx,
            "topics": ["Прочее"],
            "description": post["text"][:50],
            "usefulness": 5,
        }
        for idx, post in enumerate(posts)
    ]


def _parse_classification_response(text: str, expected_count: int) -> list[dict]:
    """Parse JSON response from Gemini."""
    # Find JSON array in response
    text = text.strip()
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        raise ClassificationError(f"No JSON array in response: {text[:200]}")

    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError as e:
        raise ClassificationError(f"Invalid JSON: {e}") from e

    results = []
    for item in data:
        results.append({
            "post_index": item.get("post_index", len(results)),
            "topics": item.get("topics", ["Прочее"]),
            "description": item.get("description", "")[:50],
            "usefulness": min(10, max(1, item.get("usefulness", 5))),
        })

    return results


async def generate_topic_summary(
    topic_name: str,
    post_descriptions: list[str],
) -> str:
    """Generate a 2-3 sentence summary for a topic."""
    if not post_descriptions:
        return ""

    descriptions_text = "\n".join(f"- {d}" for d in post_descriptions[:30])
    prompt = TOPIC_SUMMARY_PROMPT.format(
        topic_name=topic_name,
        post_descriptions=descriptions_text,
    )

    try:
        c = _get_client()
        response = await asyncio.wait_for(
            asyncio.to_thread(
                c.models.generate_content,
                model=GEMINI_MODEL,
                contents=prompt,
            ),
            timeout=30,
        )
        return response.text.strip()[:300]
    except asyncio.TimeoutError:
        logger.error("Topic summary timeout for '%s'", topic_name)
    except Exception as e:
        logger.error("Topic summary error for '%s': %s", topic_name, e)
    return ""
