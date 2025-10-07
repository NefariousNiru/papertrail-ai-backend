# repository/verification_repository.py
from typing import Final, Optional
from redis.asyncio import Redis
from config.cache import get_redis
from config.settings import settings
from model.api import VerifyClaimResponse
from repository.namespaces import VERIFICATIONS

KEY_PREFIX: Final[str] = VERIFICATIONS


class VerificationRepository:
    """
    Flow:
    - Persist backend-generated verification results per (jobId, claimId).
    - TTL 2h; refreshed on set/get to keep it alive during active sessions.
    - We DO NOT store user choices like "skip".
    """

    def __init__(self, ttl_seconds: int = settings.PERSISTENCE_TTL_SECONDS) -> None:
        self._ttl = int(ttl_seconds)

    @staticmethod
    async def _client() -> Redis:
        return await get_redis()

    @staticmethod
    def _key(job_id: str, claim_id: str) -> str:
        return f"{KEY_PREFIX}:{job_id}:{claim_id}"

    async def set(self, job_id: str, data: VerifyClaimResponse) -> None:
        r = await self._client()
        payload = data.model_dump_json(exclude_none=True).encode("utf-8")
        await r.set(self._key(job_id, data.claimId), payload, ex=self._ttl)

    async def get(self, job_id: str, claim_id: str) -> Optional[VerifyClaimResponse]:
        r = await self._client()
        raw = await r.get(self._key(job_id, claim_id))
        if raw is None:
            return None
        try:
            obj = VerifyClaimResponse.model_validate_json(raw)
        finally:
            # Refresh TTL on read
            await r.expire(self._key(job_id, claim_id), self._ttl)
        return obj

    async def clear_job(self, job_id: str) -> int:
        # Optional utility if you later want to prune all verifications for a job.
        # Can be implemented with SCAN/DEL; omitted for brevity.
        return 0
