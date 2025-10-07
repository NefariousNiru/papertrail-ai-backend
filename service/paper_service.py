# service/paper_service.py
from fastapi import UploadFile
from core.streaming import make_demo_stream, ndjson_line
from model.api import VerifyClaimResponse, StreamEvent, ProgressPayload
from model.claim import Verdict, Evidence
from repository.claim_buffer_repository import ClaimBufferRepository
from repository.job_repository import JobRepository
from repository.verification_repository import VerificationRepository
from util import functions


class PaperService:
    """
    Flow:
    - On upload: create job id; clear stale buffers.
    - On stream: replay buffered claims (overlaying verification if present),
      then continue live stream (also overlaying).
    - On verify: compute result (demo), persist to Redis (2h TTL), return to client.
    - "Skip" is a UI-only concept and is NOT persisted here.
    """

    def __init__(
        self,
        jobs: JobRepository,
        buffer: ClaimBufferRepository,
        verifications: VerificationRepository,
    ) -> None:
        self._jobs = jobs
        self._buffer = buffer
        self._verifications = verifications

    async def create_job_for_file(self, file: UploadFile) -> str:
        job = await self._jobs.create(initial_status="streaming")
        await self._buffer.clear(job.id)
        return job.id

    async def stream_claims(self, job_id: str):
        job = await self._jobs.get(job_id)
        if job is None:
            yield ndjson_line(
                StreamEvent(
                    type="error", payload={"message": "Unknown or expired jobId"}
                ).model_dump()
            )
            yield ndjson_line(StreamEvent(type="done", payload={}).model_dump())
            return

        # 0) Emit latest page-based snapshot FIRST (replay-friendly)
        snap = await self._jobs.get_progress_snapshot(job_id)
        if snap and snap.get("total", 0) > 0:
            payload = ProgressPayload.model_validate(snap)
            evt = StreamEvent(
                type="progress", payload=payload.model_dump()
            ).model_dump()
            yield ndjson_line(evt)

        # 1) Replay buffered claims (overlay verification if exists)
        buffered = await self._buffer.all(job_id)
        if buffered:
            for idx, c in enumerate(buffered, start=1):
                await self._buffer.touch(job_id)
                merged = c.model_dump(exclude_none=True)
                saved = await self._verifications.get(job_id, c.id)
                if saved:
                    functions.stream_merge_saved(merged=merged, saved=saved)
                yield ndjson_line(
                    StreamEvent(type="claim", payload=merged).model_dump()
                )
                yield ndjson_line(
                    StreamEvent(
                        type="progress",
                        payload={"processed": idx, "total": max(idx, len(buffered))},
                    ).model_dump()
                )

        # 2) Continue live stream, skipping replayed ids; overlay verification as well
        skip_ids = {c.id for c in buffered} if buffered else set()
        async for chunk in make_demo_stream(
            job_id=job_id,
            jobs=self._jobs,
            buffer=self._buffer,
            verifications=self._verifications,
            skip_ids=skip_ids,
        ):
            yield chunk

    async def verify_claim(
        self, job_id: str, claim_id: str, file: UploadFile
    ) -> VerifyClaimResponse:
        # DEMO verdict; replace with real verification later
        verdict = {
            0: Verdict.supported,
            1: Verdict.partially_supported,
            2: Verdict.unsupported,
        }[abs(hash(claim_id)) % 3]

        raw_excerpt = (
            "This is a demo excerpt of the relevant passage supporting the claim. "
            "In production, this would be a slice of the cited PDF around the matched passage."
        )
        evidence = [
            Evidence(
                paperTitle=file.filename or "Source PDF",
                page=3,  # demo placeholder
                section="Results",  # demo placeholder
                paragraph=2,  # demo placeholder
                excerpt=functions.clip_words(raw_excerpt, max_words=100),
            )
        ]
        result = VerifyClaimResponse(
            claimId=claim_id,
            verdict=verdict,
            confidence=0.82 if verdict == Verdict.supported else 0.55,
            reasoningMd="Automated check found relevant passages (demo).",
            evidence=evidence,
        )
        # Persist the verification so refresh/replay shows it
        await self._verifications.set(job_id, result)
        return result
