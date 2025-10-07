# repository/job_repository.py
from typing import Final, Optional
from uuid import uuid4
from redis.asyncio import Redis
from config.cache import get_redis
from config.settings import settings
from model.job import Job, JobStatus
from repository.namespaces import JOBS

KEY_PREFIX: Final[str] = JOBS
DEFAULT_TTL_SECONDS: Final[int] = settings.PERSISTENCE_TTL_SECONDS


class JobRepository:
    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self._ttl = int(ttl_seconds)

    @staticmethod
    async def _client() -> Redis:
        return await get_redis()

    @staticmethod
    def _key(job_id: str) -> str:
        return f"{KEY_PREFIX}:{job_id}"

    async def create(self, *, initial_status: JobStatus = "streaming") -> Job:
        # Flow: generate new job, persist with TTL, return typed model.
        job = Job(id=str(uuid4()), status=initial_status, processed=0, total=0)
        await self.put(job)
        return job

    async def put(self, job: Job) -> None:
        payload = job.model_dump_json(
            by_alias=False, exclude_none=True
        )
        r = await self._client()
        await r.set(self._key(job.id), payload.encode("utf-8"), ex=self._ttl)

    async def get(self, job_id: str) -> Optional[Job]:
        if not job_id:
            return None
        r = await self._client()
        raw = await r.get(self._key(job_id))
        if raw is None:
            return None
        try:
            return Job.model_validate_json(raw)
        except Exception:
            return None

    async def touch(self, job_id: str) -> bool:
        if not job_id:
            return False
        r = await self._client()
        return bool(await r.expire(self._key(job_id), self._ttl))

    async def delete(self, job_id: str) -> int:
        if not job_id:
            return 0
        r = await self._client()
        return int(await r.delete(self._key(job_id)))
