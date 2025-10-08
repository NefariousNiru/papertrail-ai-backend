# service/paper_service.py
from fastapi import UploadFile
from config.settings import settings
from core.pdf_text import extract_pages_texts
from core.streaming import make_live_stream, ndjson_line
from core.verification_pipeline import verify_claim_against_pdf
from model.api import VerifyClaimResponse, StreamEvent, ProgressPayload
from model.claim import Evidence, Verdict
from repository.blob_repository import BlobRepository
from repository.claim_buffer_repository import ClaimBufferRepository
from repository.job_repository import JobRepository
from repository.verification_repository import VerificationRepository
from util import functions


class PaperService:
    def __init__(
        self,
        jobs: JobRepository,
        buffer: ClaimBufferRepository,
        verifications: VerificationRepository,
        blobs: BlobRepository,
    ) -> None:
        self._jobs = jobs
        self._buffer = buffer
        self._verifications = verifications
        self._blobs = blobs

    async def create_job_for_file(self, file: UploadFile) -> str:
        job = await self._jobs.create(initial_status="streaming")
        await self._buffer.clear(job.id)
        data = await file.read()
        await file.seek(0)
        await self._blobs.put_pdf(job.id, data)
        return job.id

    async def stream_claims(self, job_id: str, api_key: str):
        """
        Replay-first strategy with status-aware behavior:
          - If job is FINISHED: emit final snapshot (if any) + replay claims, then DONE (no re-extract).
          - If job is IN-PROGRESS:
              * emit latest snapshot once (parse OR extract)
              * replay any buffered claims (overlay verification)
              * continue live extraction, skipping buffered ids
        """
        job = await self._jobs.get(job_id)
        if job is None:
            yield ndjson_line(
                StreamEvent(
                    type="error", payload={"message": "Unknown or expired jobId"}
                ).model_dump()
            )
            yield ndjson_line(StreamEvent(type="done", payload={}).model_dump())
            return

        # Read current status & latest snapshot (parse or extract)
        status = await self._jobs.get_status(job_id) or job.status
        snap = await self._jobs.get_progress_snapshot(job_id)

        # Emit the latest snapshot (if any) so UI shows correct phase/progress immediately
        if snap and snap.get("total", 0) > 0:
            payload = ProgressPayload.model_validate(snap)
            yield ndjson_line(
                StreamEvent(type="progress", payload=payload.model_dump()).model_dump()
            )

        # Pull any buffered claims
        buffered = await self._buffer.all(job_id)
        if buffered:
            # Replay buffered claims with verification overlay
            for c in buffered:
                await self._buffer.touch(job_id)
                merged = c.model_dump(exclude_none=True)
                saved = await self._verifications.get(job_id, c.id)
                if saved:
                    functions.stream_merge_saved(merged=merged, saved=saved)
                yield ndjson_line(
                    StreamEvent(type="claim", payload=merged).model_dump()
                )

        # If job has already finished, never re-run extraction.
        if (status or "").lower() == "finished":
            yield ndjson_line(StreamEvent(type="done", payload={}).model_dump())
            return

        # Otherwise, continue live extraction FROM HERE.
        pdf = await self._blobs.get_pdf(job_id)
        if not pdf:
            yield ndjson_line(StreamEvent(type="done", payload={}).model_dump())
            return

        pages = extract_pages_texts(pdf)
        if not pages:
            yield ndjson_line(StreamEvent(type="done", payload={}).model_dump())
            return

        # Skip ids we already replayed; suppress parse phase if snapshot says we're already extracting
        skip_ids = {c.id for c in buffered} if buffered else set()
        emit_parse = not (snap and snap.get("phase") == "extract")

        async for chunk in make_live_stream(
            job_id=job_id,
            api_key=api_key,
            jobs=self._jobs,
            buffer=self._buffer,
            verifications=self._verifications,
            pages=pages,
            extract_model=settings.ANTHROPIC_MODEL,
            extract_api_url=settings.ANTHROPIC_API_URL,
            extract_concurrency=settings.EXTRACT_CONCURRENCY,
            skip_ids=skip_ids,
            emit_parse=emit_parse,
        ):
            yield chunk

    async def verify_claim(
        self, job_id: str, claim_id: str, file: UploadFile, api_key: str
    ) -> VerifyClaimResponse:
        buffered = await self._buffer.all(job_id)
        claim_text = next((c.text for c in buffered if c.id == claim_id), claim_id)

        source_bytes = await file.read()
        await file.seek(0)

        v, evidence_items = await verify_claim_against_pdf(
            claim_text=claim_text,
            source_pdf_bytes=source_bytes,
            api_key=api_key,
            k=4,
        )

        verdict_map = {
            "supported": Verdict.supported,
            "partially_supported": Verdict.partially_supported,
            "unsupported": Verdict.unsupported,
        }
        verdict = verdict_map.get(v.verdict, Verdict.unsupported)

        result = VerifyClaimResponse(
            claimId=claim_id,
            verdict=verdict,
            confidence=v.confidence,
            reasoningMd=v.reasoning_md or "Automated verification result.",
            evidence=[
                Evidence(
                    paperTitle=file.filename or "Source PDF",
                    page=e.get("page"),
                    section=e.get("section"),
                    paragraph=e.get("paragraph"),
                    excerpt=e.get("excerpt"),
                )
                for e in evidence_items
            ],
        )
        await self._verifications.set(job_id, result)
        return result
