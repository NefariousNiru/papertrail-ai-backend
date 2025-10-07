# config/cache.py
from typing import Optional
from redis.asyncio import Redis, from_url
from config.settings import settings

_client: Optional[Redis] = None


async def get_redis() -> Redis:
    global _client
    if _client is None:
        _client = from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=False,  # repositories get raw bytes
            socket_keepalive=True,
            health_check_interval=30,
        )
        # Fail fast on startup if Redis is unreachable.
        await _client.ping()
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
