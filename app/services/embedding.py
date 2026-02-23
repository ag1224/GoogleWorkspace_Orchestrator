from __future__ import annotations

import logging
import json

from openai import AsyncOpenAI

from app.config import get_settings
from app.cache.redis_client import cache_get, cache_set

logger = logging.getLogger(__name__)
settings = get_settings()

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


async def generate_embedding(text: str) -> list[float]:
    """Generate embedding for a single text, with Redis caching."""
    cached = await cache_get("emb", text)
    if cached is not None:
        return json.loads(cached)

    client = _get_client()
    response = await client.embeddings.create(
        model=settings.embedding_model,
        input=text,
        dimensions=settings.embedding_dimensions,
    )
    embedding = response.data[0].embedding

    await cache_set("emb", text, json.dumps(embedding), ttl=settings.embedding_cache_ttl)
    return embedding


async def generate_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a batch of texts. Uses cache where possible."""
    results: list[list[float] | None] = [None] * len(texts)
    uncached_indices: list[int] = []
    uncached_texts: list[str] = []

    for i, text in enumerate(texts):
        cached = await cache_get("emb", text)
        if cached is not None:
            results[i] = json.loads(cached)
        else:
            uncached_indices.append(i)
            uncached_texts.append(text)

    if uncached_texts:
        client = _get_client()
        # OpenAI supports up to 2048 inputs per batch
        for batch_start in range(0, len(uncached_texts), 2048):
            batch = uncached_texts[batch_start : batch_start + 2048]
            batch_indices = uncached_indices[batch_start : batch_start + 2048]

            response = await client.embeddings.create(
                model=settings.embedding_model,
                input=batch,
                dimensions=settings.embedding_dimensions,
            )
            for j, item in enumerate(response.data):
                idx = batch_indices[j]
                results[idx] = item.embedding
                await cache_set("emb", texts[idx], json.dumps(item.embedding), ttl=settings.embedding_cache_ttl)

    return results  # type: ignore[return-value]


def build_email_text(subject: str, sender: str, body_preview: str) -> str:
    return f"{subject} | From: {sender} | {body_preview[:500]}"


def build_event_text(title: str, description: str | None, attendees: list[str] | None) -> str:
    parts = [title]
    if description:
        parts.append(description[:300])
    if attendees:
        parts.append(f"Attendees: {', '.join(attendees)}")
    return " | ".join(parts)


def build_file_text(name: str, mime_type: str | None, content_preview: str | None) -> str:
    parts = [name]
    if mime_type:
        parts.append(mime_type)
    if content_preview:
        parts.append(content_preview[:500])
    return " | ".join(parts)
