# repository/claim_buffer_repository.py
from typing import List
from redis.asyncio import Redis
from config.cache import get_redis
from config.settings import settings
from model.claim import Claim
from repository.namespaces import CLAIMS


class ClaimBufferRepository:
    """
    Flow:
    - Append each emitted claim to a Redis list (RPUSH) keyed by jobId.
    - On refresh, replay list contents before continuing the live stream.
    - TTL is refreshed on append/read so the buffer survives active sessions.
    """

    def __init__(self, ttl_seconds: int = settings.PERSISTENCE_TTL_SECONDS) -> None:
        self._ttl = int(ttl_seconds)

    @staticmethod
    def _key(job_id: str) -> str:
        return f"{CLAIMS}:{job_id}"

    @staticmethod
    async def _client() -> Redis:
        return await get_redis()

    async def append(self, job_id: str, claim: Claim) -> None:
        r = await self._client()
        payload = claim.model_dump_json(exclude_none=True).encode("utf-8")
        await r.rpush(self._key(job_id), payload)
        await r.expire(self._key(job_id), self._ttl)

    async def all(self, job_id: str) -> List[Claim]:
        r = await self._client()
        vals = await r.lrange(self._key(job_id), 0, -1)
        out: List[Claim] = []
        for raw in vals or []:
            try:
                out.append(Claim.model_validate_json(raw))
            except Exception:
                # Skip malformed entries instead of breaking the stream
                continue
        if vals is not None:
            await r.expire(self._key(job_id), self._ttl)
        return out

    async def count(self, job_id: str) -> int:
        r = await self._client()
        n = await r.llen(self._key(job_id))
        if n and n > 0:
            await r.expire(self._key(job_id), self._ttl)
        return int(n or 0)

    async def clear(self, job_id: str) -> int:
        r = await self._client()
        return int(await r.delete(self._key(job_id)))

    async def touch(self, job_id: str) -> bool:
        r = await self._client()
        return bool(await r.expire(self._key(job_id), self._ttl))
