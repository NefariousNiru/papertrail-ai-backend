# core/streaming.py
from model.claim import Claim
from repository.claim_buffer_repository import ClaimBufferRepository
from repository.job_repository import JobRepository
import json
from typing import AsyncIterator, Dict, Final, Iterable

LINE_SEP: Final[str] = "\n"


def ndjson_line(obj: Dict[str, object]) -> bytes:
    return (json.dumps(obj, separators=(",", ":")) + LINE_SEP).encode("utf-8")


async def make_demo_stream(
    job_id: str,
    jobs: JobRepository,
    buffer: ClaimBufferRepository,
    skip_ids: Iterable[str] | None = None,
) -> AsyncIterator[bytes]:
    from asyncio import sleep

    skip: set[str] = set(skip_ids or [])

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

    total = len(demo_claims)
    processed = 0

    for claim_dict in demo_claims:
        # Keep the job alive while the user is connected
        await jobs.touch(job_id)

        if claim_dict["id"] in skip:
            processed += 1
            continue  # this one was already replayed; don't re-send

        # Persist to buffer first so reconnects can replay
        await buffer.append(job_id, Claim(**claim_dict))

        processed += 1
        yield ndjson_line({"type": "claim", "payload": claim_dict})
        yield ndjson_line(
            {"type": "progress", "payload": {"processed": processed, "total": total}}
        )
        await sleep(0.35)

    yield ndjson_line({"type": "done"})
