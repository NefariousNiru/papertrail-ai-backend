# core/streaming.py
import time
from typing import AsyncIterator, Dict, Final, Iterable, List, Tuple
from core.anthropic_client import extract_claims_from_page
from model.api import ProgressPayload, StreamEvent, ProgressPhase
from model.claim import Claim
from repository.claim_buffer_repository import ClaimBufferRepository
from repository.job_repository import JobRepository
from repository.verification_repository import VerificationRepository
from util import functions
import json
from asyncio import Semaphore, create_task, as_completed

LINE_SEP: Final[str] = "\n"


def ndjson_line(obj: Dict[str, object]) -> bytes:
    """
    Compact NDJSON serialization helper for SSE-like streaming.
    """
    return (json.dumps(obj, separators=(",", ":")) + LINE_SEP).encode("utf-8")


async def _merge_verification(
    verifications: VerificationRepository, job_id: str, claim_dict: Dict[str, object]
) -> Dict[str, object]:
    """
    Merge any saved verification result into the live claim payload.
    """
    cid = str(claim_dict.get("id") or "")
    if not cid:
        return claim_dict
    saved = await verifications.get(job_id, cid)
    if saved:
        functions.stream_merge_saved(merged=claim_dict, saved=saved)
    return claim_dict


async def _emit_phase_progress(
    *,
    job_id: str,
    jobs: JobRepository,
    phase: ProgressPhase,
    processed: int,
    total: int,
) -> bytes:
    """Persist and emit a phase progress snapshot (parse/extract)."""
    await jobs.save_phase_progress(
        job_id, phase=phase, processed=processed, total=total
    )
    payload = ProgressPayload(
        phase=phase, processed=processed, total=total, ts=int(time.time())
    )
    event = StreamEvent(type="progress", payload=payload.model_dump())
    return ndjson_line(event.model_dump())


async def make_live_stream(
    *,
    job_id: str,
    api_key: str,
    jobs: JobRepository,
    buffer: ClaimBufferRepository,
    verifications: VerificationRepository,
    pages: List[Tuple[int, str]],
    extract_model: str,
    extract_api_url: str,
    extract_concurrency: int,
    skip_ids: Iterable[str] | None = None,
    emit_parse: bool = True,
    extract_start_processed: int = 0,
) -> AsyncIterator[bytes]:
    """
    Drive concurrent, per-page claim extraction and emit NDJSON events:
      - progress events for parse and extract phases
      - claim events as they arrive
      - final done event
      - emit_parse: if False, skip emitting the parse phase (useful on reconnect in extract phase).
      - extract_start_processed: resume counter for extract progress on reconnect.
    """
    skip = set(skip_ids or [])
    total_pages = len(pages)

    # -------- Phase: PARSE (0..N) --------
    if emit_parse:
        for i in range(total_pages + 1):
            yield await _emit_phase_progress(
                job_id=job_id, jobs=jobs, phase="parse", processed=i, total=total_pages
            )

    # -------- Phase: EXTRACT (concurrent per-page) --------
    sem = Semaphore(max(1, extract_concurrency))
    tasks = []

    async def _one_page(pn: int, text: str):
        async with sem:
            claims = await extract_claims_from_page(
                api_key=api_key,
                model=extract_model,
                api_url=extract_api_url,
                page_number=pn,
                page_text=text,
            )
            out: List[Dict[str, object]] = []
            for c in claims:
                out.append(
                    {
                        "id": c.get("id") or f"p{pn}_{len(out) + 1}",
                        "text": c.get("text"),
                        "status": c.get("status") or "uncited",
                        "verdict": None,
                        "confidence": None,
                        "suggestions": [],
                        "sourceUploaded": False,
                    }
                )
            return pn, out

    for pn, txt in pages:
        tasks.append(create_task(_one_page(pn, txt)))

    finished_pages = int(max(0, extract_start_processed))
    for fut in as_completed(tasks):
        pn, claim_list = await fut
        await jobs.touch(job_id)

        # Stream each claim as soon as its page finishes
        for cdict in claim_list:
            if cdict["id"] in skip:
                continue
            await buffer.append(job_id, Claim(**cdict))
            merged = await _merge_verification(verifications, job_id, dict(cdict))
            evt = StreamEvent(type="claim", payload=merged)
            yield ndjson_line(evt.model_dump())

        # Emit extract progress (typed + persisted)
        finished_pages += 1
        yield await _emit_phase_progress(
            job_id=job_id,
            jobs=jobs,
            phase="extract",
            processed=finished_pages,
            total=total_pages,
        )

    # -------- DONE --------
    yield ndjson_line(StreamEvent(type="done", payload={}).model_dump())
