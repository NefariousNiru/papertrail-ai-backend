# repository/job_repository.py
import time
from typing import Final, Optional
from uuid import uuid4
from redis.asyncio import Redis
from config.cache import get_redis
from config.settings import settings
from model.api import ProgressPhase
from model.job import Job, JobStatus
from repository.namespaces import JOBS

KEY_PREFIX: Final[str] = JOBS


class JobRepository:
    def __init__(self, ttl_seconds: int = settings.PERSISTENCE_TTL_SECONDS) -> None:
        self._ttl = int(ttl_seconds)

    @staticmethod
    async def _client() -> Redis:
        return await get_redis()

    @staticmethod
    def _key(job_id: str) -> str:
        return f"{KEY_PREFIX}:{job_id}"

    # ---------------- Core CRUD ----------------

    async def create(self, *, initial_status: JobStatus = "streaming") -> Job:
        job = Job(id=str(uuid4()), status=initial_status, processed=0, total=0)
        await self.put(job)
        return job

    async def put(self, job: Job) -> None:
        r = await self._client()
        mapping = {
            "id": job.id,
            "status": job.status,
            "processed": str(job.processed or 0),
            "total": str(job.total or 0),
        }
        await r.hset(self._key(job.id), mapping=mapping)
        await r.expire(self._key(job.id), self._ttl)

    async def get(self, job_id: str) -> Optional[Job]:
        if not job_id:
            return None
        r = await self._client()
        h = await r.hgetall(self._key(job_id))
        if not h:
            return None

        def _s(key: str, default: str = "") -> str:
            v = h.get(key)
            if v is None:
                return default
            return v.decode("utf-8") if isinstance(v, (bytes, bytearray)) else str(v)

        try:
            return Job(
                id=_s("id"),
                status=_s("status") or "streaming",
                processed=int(_s("processed", "0") or 0),
                total=int(_s("total", "0") or 0),
            )
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

    # ---------------- Status helpers ----------------

    async def set_status(self, job_id: str, status: JobStatus) -> None:
        r = await self._client()
        await r.hset(self._key(job_id), mapping={"status": status})
        await r.expire(self._key(job_id), self._ttl)

    async def get_status(self, job_id: str) -> Optional[JobStatus]:
        r = await self._client()
        v = await r.hget(self._key(job_id), "status")
        if v is None:
            return None
        if isinstance(v, (bytes, bytearray)):
            v = v.decode("utf-8")
        return v or None

    async def set_totals(self, job_id: str, *, processed: int, total: int) -> None:
        r = await self._client()
        await r.hset(
            self._key(job_id),
            mapping={"processed": str(processed), "total": str(total)},
        )
        await r.expire(self._key(job_id), self._ttl)

    # ---------------- Phase-based progress snapshots (parse/extract) ----------------

    async def save_phase_progress(
        self, job_id: str, *, phase: ProgressPhase, processed: int, total: int
    ) -> None:
        """
        Persist snapshot for any phase; also mirror processed/total for quick inspection.
        Newer snapshots overwrite older ones (we keep only the latest).
        """
        now = int(time.time())
        r = await self._client()
        await r.hset(
            self._key(job_id),
            mapping={
                "phase": phase,
                "progress_processed": str(processed),
                "progress_total": str(total),
                "progress_ts": str(now),
                "processed": str(processed),
                "total": str(total),
            },
        )
        await r.expire(self._key(job_id), self._ttl)

    async def get_progress_snapshot(self, job_id: str) -> dict | None:
        """
        Return the latest saved snapshot (parse OR extract), or None.
        """
        r = await self._client()
        h = await r.hgetall(self._key(job_id))
        if not h:
            return None

        def _s(key: str) -> Optional[str]:
            v = h.get(key)
            if v is None:
                return None
            return v.decode("utf-8") if isinstance(v, (bytes, bytearray)) else str(v)

        phase = _s("phase")
        if not phase:
            return None

        try:
            processed = int((_s("progress_processed") or "0"))
            total = int((_s("progress_total") or "0"))
            ts = int(_s("progress_ts") or str(int(time.time())))
            return {"phase": phase, "processed": processed, "total": total, "ts": ts}
        except Exception:
            return None
