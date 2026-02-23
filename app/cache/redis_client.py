from __future__ import annotations

import hashlib
import json
import logging

import redis.asyncio as redis

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_pool: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    global _pool
    if _pool is None:
        _pool = redis.from_url(settings.redis_url, decode_responses=True)
    return _pool


async def close_redis() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def _hash_key(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:32]


async def cache_get(prefix: str, key: str) -> str | None:
    r = await get_redis()
    return await r.get(f"{prefix}:{_hash_key(key)}")


async def cache_set(prefix: str, key: str, value: str, ttl: int | None = None) -> None:
    r = await get_redis()
    full_key = f"{prefix}:{_hash_key(key)}"
    if ttl:
        await r.setex(full_key, ttl, value)
    else:
        await r.set(full_key, value)


async def cache_get_json(prefix: str, key: str) -> dict | list | None:
    raw = await cache_get(prefix, key)
    if raw is not None:
        return json.loads(raw)
    return None


async def cache_set_json(prefix: str, key: str, value: dict | list, ttl: int | None = None) -> None:
    await cache_set(prefix, key, json.dumps(value, default=str), ttl)


async def rate_limit_check(user_id: str, limit: int = 100, window: int = 3600) -> bool:
    """Returns True if request is allowed, False if rate limited."""
    r = await get_redis()
    key = f"rl:{user_id}"
    current = await r.get(key)
    if current is not None and int(current) >= limit:
        return False
    pipe = r.pipeline()
    pipe.incr(key)
    pipe.expire(key, window)
    await pipe.execute()
    return True


async def store_conversation_context(user_id: str, query: str, max_entries: int = 5) -> list[str]:
    """Store query in conversation context and return recent queries."""
    r = await get_redis()
    key = f"ctx:{user_id}"
    await r.lpush(key, query)
    await r.ltrim(key, 0, max_entries - 1)
    await r.expire(key, settings.conversation_context_ttl)
    return await r.lrange(key, 0, -1)


async def get_conversation_context(user_id: str) -> list[str]:
    r = await get_redis()
    return await r.lrange(f"ctx:{user_id}", 0, -1)
