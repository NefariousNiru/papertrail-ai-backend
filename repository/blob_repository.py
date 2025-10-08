# repository/blob_repository.py
from typing import Optional
from redis.asyncio import Redis
from config.cache import get_redis
from config.settings import settings
from repository.namespaces import BLOBS


class BlobRepository:
    """
    Redis-backed byte storage for original uploaded PDFs keyed by job_id.

    TTL is refreshed by touch(job_id) during active sessions.
    """

    def __init__(self, ttl_seconds: int = settings.PERSISTENCE_TTL_SECONDS) -> None:
        self._ttl = int(ttl_seconds)

    @staticmethod
    async def _client() -> Redis:
        return await get_redis()

    @staticmethod
    def _key(job_id: str) -> str:
        return f"{BLOBS}:{job_id}"

    async def put_pdf(self, job_id: str, data: bytes) -> None:
        r = await self._client()
        await r.set(self._key(job_id), data, ex=self._ttl)

    async def get_pdf(self, job_id: str) -> Optional[bytes]:
        r = await self._client()
        raw = await r.get(self._key(job_id))
        return raw if raw is not None else None

    async def touch(self, job_id: str) -> bool:
        r = await self._client()
        return bool(await r.expire(self._key(job_id), self._ttl))

    async def delete(self, job_id: str) -> int:
        r = await self._client()
        return int(await r.delete(self._key(job_id)))
