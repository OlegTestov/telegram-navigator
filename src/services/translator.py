"""Translate LLM-generated content between languages via Gemini."""

import asyncio
import logging
import re

from google import genai

from src.config.prompts import TRANSLATION_PROMPT, get_language_name
from src.config.settings import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


async def translate_texts(texts: list[str], target_lang: str = "en") -> list[str]:
    """Batch-translate texts to target language via Gemini.

    Args:
        texts: List of texts to translate.
        target_lang: Language code (e.g., "en", "ru") or language name (e.g., "English").

    Returns list of same length as input. On failure, returns original texts.
    Skips empty strings (returns them as-is).
    """
    if not texts:
        return []

    # Filter out empty strings, remember their positions
    indexed = [(i, t) for i, t in enumerate(texts) if t and t.strip()]
    if not indexed:
        return list(texts)

    # Resolve language code to name if needed
    lang_name = get_language_name(target_lang) if len(target_lang) <= 3 else target_lang

    to_translate = [t for _, t in indexed]
    numbered = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(to_translate))
    prompt = TRANSLATION_PROMPT.format(
        count=len(to_translate),
        target_lang=lang_name,
        texts=numbered,
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
        translated = _parse_numbered_list(response.text, len(to_translate))
    except asyncio.TimeoutError:
        logger.error("Translation timeout for %d texts", len(to_translate))
        return list(texts)
    except Exception as e:
        logger.error("Translation error: %s", e)
        return list(texts)

    if len(translated) != len(to_translate):
        logger.warning("Translation count mismatch: expected %d, got %d", len(to_translate), len(translated))
        return list(texts)

    # Reconstruct the full list with translations in correct positions
    result = list(texts)
    for (orig_idx, _), tr in zip(indexed, translated):
        result[orig_idx] = tr

    return result


def _parse_numbered_list(text: str, expected_count: int) -> list[str]:
    """Parse a numbered list response from Gemini."""
    lines = re.findall(r"^\d+\.\s*(.+)", text, re.MULTILINE)
    if lines:
        return [line.strip() for line in lines]
    # Fallback: split by newlines
    lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
    return lines
