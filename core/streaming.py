# core/streaming.py
import time

from model.api import ProgressPayload, StreamEvent, ProgressPhase
from model.claim import Claim
from repository.claim_buffer_repository import ClaimBufferRepository
from repository.job_repository import JobRepository
import json
from typing import AsyncIterator, Dict, Final, Iterable
from repository.verification_repository import VerificationRepository
from util import functions

LINE_SEP: Final[str] = "\n"


def ndjson_line(obj: Dict[str, object]) -> bytes:
    return (json.dumps(obj, separators=(",", ":")) + LINE_SEP).encode("utf-8")


def make_progress_event(
    *,
    phase: ProgressPhase,
    processed: int,
    total: int,
    ts: int | None = None,
) -> Dict[str, object]:
    """Builds and validates a progress StreamEvent, returns a plain dict ready for NDJSON."""
    payload = ProgressPayload(
        phase=phase, processed=processed, total=total, ts=int(ts or time.time())
    )
    event = StreamEvent(type="progress", payload=payload.model_dump())
    return event.model_dump()


async def _merge_verification(
    verifications: VerificationRepository,
    job_id: str,
    claim_dict: Dict[str, object],
) -> Dict[str, object]:
    """Overlay saved verification so refresh/replay emits verified fields."""
    claim_id = str(claim_dict.get("id") or "")
    if not claim_id:
        return claim_dict
    saved = await verifications.get(job_id, claim_id)
    if not saved:
        return claim_dict

    # Overlay backend-generated fields
    functions.stream_merge_saved(merged=claim_dict, saved=saved)
    return claim_dict


async def _emit_parse_progress(
    *,
    job_id: str,
    jobs: JobRepository,
    processed: int,
    total: int,
) -> bytes:
    # Persist snapshot for replay, then emit NDJSON line
    await jobs.save_parse_progress(job_id, processed=processed, total=total)
    evt = make_progress_event(phase="parse", processed=processed, total=total)
    return ndjson_line(evt)


async def make_demo_stream(
    job_id: str,
    jobs: JobRepository,
    buffer: ClaimBufferRepository,
    verifications: VerificationRepository,
    skip_ids: Iterable[str] | None = None,
) -> AsyncIterator[bytes]:
    """
    Demo pipeline:
      1) Page-aware parsing with determinate progress:
         - Emits {"type":"progress","payload":{"phase":"parse","processed","total","ts"}}
         - Persists snapshot via JobRepository.save_parse_progress so reconnect shows it first.
      2) Stream demo claims (skipping any already buffered ids) with verification overlay and buffering for replay.
    """
    from asyncio import sleep

    skip: set[str] = set(skip_ids or [])

    # ---------- 1) Page-based parse progress (demo) ----------
    total_pages = 12  # Replace with real doc.page_count in production
    yield await _emit_parse_progress(
        job_id=job_id, jobs=jobs, processed=0, total=total_pages
    )

    for p in range(1, total_pages + 1):
        await sleep(0.05)  # simulate per-page parse latency
        yield await _emit_parse_progress(
            job_id=job_id, jobs=jobs, processed=p, total=total_pages
        )

    # ---------- 2) Claim streaming with overlay + buffering ----------
    demo_claims = [
        {
            "id": "c1",
            "text": "Transformers outperform RNNs on translation tasks.",
            "status": "cited",
            "verdict": None,
            "confidence": None,
            "suggestions": [],
            "sourceUploaded": False,
        },
        {
            "id": "c2",
            "text": "Pretraining improves zero-shot performance in most language tasks.",
            "status": "weakly_cited",
            "verdict": None,
        },
        {
            "id": "c3",
            "text": "Graph neural networks strictly dominate CNNs for all vision tasks.",
            "status": "uncited",
            "verdict": None,
            "suggestions": [
                {
                    "title": "CNN vs GNN survey",
                    "url": "https://example.org/survey",
                    "venue": "TPAMI",
                    "year": 2020,
                }
            ],
        },
    ]

    for claim_dict in demo_claims:
        await jobs.touch(job_id)

        if claim_dict["id"] in skip:
            continue

        # Buffer original claim so reconnects can replay
        await buffer.append(job_id, Claim(**claim_dict))

        # Overlay any existing verification result before emitting
        merged = await _merge_verification(verifications, job_id, dict(claim_dict))

        # Emit claim
        claim_evt = StreamEvent(type="claim", payload=merged).model_dump()
        yield ndjson_line(claim_evt)
        await sleep(0.35)

    done_evt = StreamEvent(type="done", payload={}).model_dump()
    yield ndjson_line(done_evt)
