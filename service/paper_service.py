# service/paper_service.py
from fastapi import UploadFile
from core.streaming import make_demo_stream
from model.api import VerifyClaimResponse
from model.claim import Verdict
from repository.job_repository import JobRepository


class PaperService:
    def __init__(self, jobs: JobRepository) -> None:
        self._jobs = jobs

    async def create_job_for_file(self, file: UploadFile) -> str:
        # In a real impl, you'd stage the file and kick off parsing here.
        job = await self._jobs.create(initial_status="streaming")
        return job.id

    async def stream_claims(self, job_id: str):
        # Delegates to an async iterator that yields NDJSON chunks.
        # If job does not exist (expired/invalid), emit an error event once.
        job = await self._jobs.get(job_id)
        if job is None:
            from core.streaming import ndjson_line

            yield ndjson_line(
                {"type": "error", "payload": {"message": "Unknown or expired jobId"}}
            )
            yield ndjson_line({"type": "done"})
            return

        async for chunk in make_demo_stream(job_id=job_id, jobs=self._jobs):
            yield chunk

    async def verify_claim(
        self, claim_id: str, file: UploadFile
    ) -> VerifyClaimResponse:
        # Demo verdict: pseudo-deterministic without external calls.
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
