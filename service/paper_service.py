# service/paper_service.py
from fastapi import UploadFile
from core.streaming import make_demo_stream, ndjson_line
from model.api import VerifyClaimResponse
from model.claim import Verdict
from repository.claim_buffer_repository import ClaimBufferRepository
from repository.job_repository import JobRepository


class PaperService:
    """
    Flow:
    - On upload: create a job id (ephemeral).
    - On stream: first replay any buffered claims (from Redis), then continue live.
    - On verify: return demo verdict (placeholder for real verification).
    """

    def __init__(self, jobs: JobRepository, buffer: ClaimBufferRepository) -> None:
        self._jobs = jobs
        self._buffer = buffer

    async def create_job_for_file(self, file: UploadFile) -> str:
        job = await self._jobs.create(initial_status="streaming")
        # New job; ensure no stale buffer exists (defensive)
        await self._buffer.clear(job.id)
        return job.id

    async def stream_claims(self, job_id: str):
        job = await self._jobs.get(job_id)
        if job is None:
            yield ndjson_line(
                {"type": "error", "payload": {"message": "Unknown or expired jobId"}}
            )
            yield ndjson_line({"type": "done"})
            return

        # 1) Replay buffered claims (if any)
        buffered = await self._buffer.all(job_id)
        if buffered:
            for idx, c in enumerate(buffered, start=1):
                # Keep buffer hot while active
                await self._buffer.touch(job_id)
                yield ndjson_line(
                    {"type": "claim", "payload": c.model_dump(exclude_none=True)}
                )
                # Optional: send a conservative progress (idx/idx) so UI shows immediate activity
                yield ndjson_line(
                    {"type": "progress", "payload": {"processed": idx, "total": idx}}
                )

        # 2) Continue live stream, skipping already replayed ids
        skip_ids = {c.id for c in buffered} if buffered else set()
        async for chunk in make_demo_stream(
            job_id=job_id, jobs=self._jobs, buffer=self._buffer, skip_ids=skip_ids
        ):
            yield chunk

    async def verify_claim(
        self, claim_id: str, file: UploadFile
    ) -> VerifyClaimResponse:
        verdict = {
            0: Verdict.supported,
            1: Verdict.partially_supported,
            2: Verdict.unsupported,
        }[abs(hash(claim_id)) % 3]

        return VerifyClaimResponse(
            claimId=claim_id,
            verdict=verdict,
            confidence=0.82 if verdict == Verdict.supported else 0.55,
            reasoningMd="Automated check found relevant passages (demo).",
        )
