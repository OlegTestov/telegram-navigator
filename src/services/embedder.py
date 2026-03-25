"""Generate embeddings using OpenAI text-embedding-3-small."""

import asyncio
import logging
import struct

from openai import OpenAI

from src.config.settings import OPENAI_API_KEY, OPENAI_EMBEDDING_MODEL, EMBEDDING_BATCH_SIZE

logger = logging.getLogger(__name__)

_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client


def serialize_float32(vector: list[float]) -> bytes:
    """Serialize a float vector to bytes for sqlite-vec."""
    return struct.pack(f"{len(vector)}f", *vector)


async def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a list of texts, batched."""
    all_embeddings = []
    for i in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[i : i + EMBEDDING_BATCH_SIZE]
        batch_embeddings = await _embed_batch(batch)
        if not batch_embeddings:
            return []  # abort on error
        all_embeddings.extend(batch_embeddings)
    return all_embeddings


async def _embed_batch(texts: list[str]) -> list[list[float]]:
    """Call OpenAI embeddings API for a single batch."""
    try:
        client = _get_client()
        response = await asyncio.to_thread(
            client.embeddings.create,
            model=OPENAI_EMBEDDING_MODEL,
            input=texts,
        )
        return [item.embedding for item in response.data]
    except Exception as e:
        logger.error("OpenAI embedding error: %s", e)
        return []


async def get_query_embedding(query: str) -> list[float] | None:
    """Get embedding for a single search query."""
    results = await generate_embeddings([query])
    return results[0] if results else None
