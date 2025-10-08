# core/streaming.py
import time
from typing import AsyncIterator, Dict, Final, Iterable, List, Tuple
from core.anthropic_client import extract_claims_from_page
from model.claim import Claim
from repository.claim_buffer_repository import ClaimBufferRepository
from repository.job_repository import JobRepository
from repository.verification_repository import VerificationRepository
from util import functions
import json
import logging
from util.timing import timed

LINE_SEP: Final[str] = "\n"
logger = logging.getLogger(__name__)


def ndjson_line(obj: Dict[str, object]) -> bytes:
    return (json.dumps(obj, separators=(",", ":")) + LINE_SEP).encode("utf-8")


async def _merge_verification(
    verifications: VerificationRepository, job_id: str, claim_dict: Dict[str, object]
) -> Dict[str, object]:
    cid = str(claim_dict.get("id") or "")
    if not cid:
        return claim_dict
    saved = await verifications.get(job_id, cid)
    if saved:
        functions.stream_merge_saved(merged=claim_dict, saved=saved)
    return claim_dict


async def _emit_phase_progress(
    *, job_id: str, jobs: JobRepository, phase: str, processed: int, total: int
) -> bytes:
    await jobs.save_phase_progress(
        job_id, phase=phase, processed=processed, total=total
    )
    return ndjson_line(
        {
            "type": "progress",
            "payload": {
                "phase": phase,
                "processed": processed,
                "total": total,
                "ts": int(time.time()),
            },
        }
    )


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
    emit_parse: bool = True,  # NEW: allows skipping parse replay on resume
) -> AsyncIterator[bytes]:
    """
    Drive concurrent, per-page claim extraction and emit NDJSON events:
      - optional parse progress (if emit_parse=True)
      - extract progress per finished page
      - claim events as they arrive
      - mark job finished at end
    """
    from asyncio import Semaphore, create_task, as_completed

    skip = set(skip_ids or [])
    total_pages = len(pages)
    logger.info(
        "stream.start job=%s pages=%d conc=%d skip=%d",
        job_id,
        total_pages,
        extract_concurrency,
        len(skip),
    )

    # Parse progress (0..N) only if requested
    if emit_parse:
        for i in range(total_pages + 1):
            yield await _emit_phase_progress(
                job_id=job_id, jobs=jobs, phase="parse", processed=i, total=total_pages
            )

    # Concurrent per-page extraction
    sem = Semaphore(max(1, extract_concurrency))
    tasks = []

    async def _one_page(pn: int, text: str):
        async with sem:
            with timed(logger, "stream.page.extract", page=pn):
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
                            "id": c.get("id") or f"p{pn}_{len(out)+1}",
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

    finished_pages = 0
    with timed(logger, "stream.extract.all", pages=total_pages):
        for fut in as_completed(tasks):
            pn, claim_list = await fut
            await jobs.touch(job_id)

            for cdict in claim_list:
                if cdict["id"] in skip:
                    continue
                await buffer.append(job_id, Claim(**cdict))
                merged = await _merge_verification(verifications, job_id, dict(cdict))
                yield ndjson_line({"type": "claim", "payload": merged})

            finished_pages += 1
            yield await _emit_phase_progress(
                job_id=job_id,
                jobs=jobs,
                phase="extract",
                processed=finished_pages,
                total=total_pages,
            )

    # Final snapshot + status
    await jobs.save_phase_progress(
        job_id, phase="extract", processed=total_pages, total=total_pages
    )
    await jobs.set_status(job_id, "finished")
    logger.info("stream.done job=%s", job_id)
    yield ndjson_line({"type": "done"})
