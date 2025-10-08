# service/paper_service.py
import logging
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

logger = logging.getLogger(__name__)


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
        """
        Create job, clear stale buffers, persist PDF bytes.
        Logs: created job id and byte size (no payloads).
        """
        job = await self._jobs.create(initial_status="streaming")
        await self._buffer.clear(job.id)
        try:
            data = await file.read()
            await file.seek(0)
        except Exception:
            logger.error("upload.read.error")
            raise
        try:
            await self._blobs.put_pdf(job.id, data)
        except Exception:
            logger.error("upload.persist.error")
            raise
        logger.info("upload.ok job=%s bytes=%d", job.id, len(data))
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
        try:
            job = await self._jobs.get(job_id)
        except Exception:
            logger.error("stream.job.get.error job=%s", job_id)
            # fall through to error payload
            job = None

        if job is None:
            yield ndjson_line(
                StreamEvent(
                    type="error", payload={"message": "Unknown or expired jobId"}
                ).model_dump()
            )
            yield ndjson_line(StreamEvent(type="done", payload={}).model_dump())
            return

        # Read current status & latest snapshot (parse or extract)
        try:
            status = await self._jobs.get_status(job_id) or job.status
            snap = await self._jobs.get_progress_snapshot(job_id)
        except Exception:
            logger.error("stream.snapshot.error job=%s", job_id)
            status = job.status
            snap = None

        # Emit the latest snapshot (if any) so UI shows correct phase/progress immediately
        if snap and snap.get("total", 0) > 0:
            try:
                payload = ProgressPayload.model_validate(snap)
                yield ndjson_line(
                    StreamEvent(
                        type="progress", payload=payload.model_dump()
                    ).model_dump()
                )
            except Exception:
                logger.error("stream.snapshot.emit.error job=%s", job_id)

        # Pull any buffered claims
        try:
            buffered = await self._buffer.all(job_id)
        except Exception:
            logger.error("stream.buffer.read.error job=%s", job_id)
            buffered = []

        if buffered:
            logger.info("stream.replay job=%s count=%d", job_id, len(buffered))
            # Replay buffered claims with verification overlay
            for c in buffered:
                try:
                    await self._buffer.touch(job_id)
                    merged = c.model_dump(exclude_none=True)
                    saved = await self._verifications.get(job_id, c.id)
                    if saved:
                        functions.stream_merge_saved(merged=merged, saved=saved)
                    yield ndjson_line(
                        StreamEvent(type="claim", payload=merged).model_dump()
                    )
                except Exception:
                    logger.error("stream.replay.error job=%s", job_id)

        # If job has already finished, never re-run extraction.
        if (status or "").lower() == "finished":
            logger.info("stream.finish.shortcircuit job=%s", job_id)
            yield ndjson_line(StreamEvent(type="done", payload={}).model_dump())
            return

        # Otherwise, continue live extraction FROM HERE.
        try:
            pdf = await self._blobs.get_pdf(job_id)
        except Exception:
            logger.error("stream.pdf.fetch.error job=%s", job_id)
            pdf = None

        if not pdf:
            logger.warning("stream.pdf.missing job=%s", job_id)
            yield ndjson_line(StreamEvent(type="done", payload={}).model_dump())
            return

        try:
            pages = extract_pages_texts(pdf)
        except Exception:
            logger.error("stream.pdf.parse.error job=%s", job_id)
            pages = []

        if not pages:
            logger.warning("stream.pages.empty job=%s", job_id)
            yield ndjson_line(StreamEvent(type="done", payload={}).model_dump())
            return

        # Skip ids we already replayed; suppress parse phase if snapshot says we're already extracting
        skip_ids = {c.id for c in buffered} if buffered else set()
        emit_parse = not (snap and snap.get("phase") == "extract")
        logger.info(
            "stream.live.start job=%s pages=%d skip=%d emit_parse=%s",
            job_id,
            len(pages),
            len(skip_ids),
            emit_parse,
        )

        try:
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
        except Exception:
            logger.error("stream.live.error job=%s", job_id)
            # Try to gracefully end the stream
            yield ndjson_line(StreamEvent(type="done", payload={}).model_dump())

    async def verify_claim(
        self, job_id: str, claim_id: str, file: UploadFile, api_key: str
    ) -> VerifyClaimResponse:
        """
        Verify a buffered claim against an uploaded source PDF and persist result.
        Logs: sizes and verdict only (no payloads).
        """
        try:
            buffered = await self._buffer.all(job_id)
        except Exception:
            logger.error("verify.buffer.read.error job=%s", job_id)
            buffered = []

        claim_text = next((c.text for c in buffered if c.id == claim_id), claim_id)

        try:
            source_bytes = await file.read()
            await file.seek(0)
        except Exception:
            logger.error("verify.file.read.error job=%s", job_id)
            raise

        logger.info(
            "verify.start job=%s claim=%s bytes=%d", job_id, claim_id, len(source_bytes)
        )

        try:
            v, evidence_items = await verify_claim_against_pdf(
                claim_text=claim_text,
                source_pdf_bytes=source_bytes,
                api_key=api_key,
                k=4,
            )
        except Exception:
            logger.error("verify.pipeline.error job=%s", job_id)
            raise

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

        try:
            await self._verifications.set(job_id, result)
        except Exception:
            logger.error("verify.persist.error job=%s claim=%s", job_id, claim_id)
            raise

        logger.info(
            "verify.ok job=%s claim=%s verdict=%s conf=%.2f",
            job_id,
            claim_id,
            verdict.value,
            v.confidence,
        )
        return result
