# core/streaming.py
from repository.job_repository import JobRepository
import json
from typing import AsyncIterator, Dict, Final

LINE_SEP: Final[str] = "\n"


def ndjson_line(obj: Dict[str, object]) -> bytes:
    return (json.dumps(obj, separators=(",", ":")) + LINE_SEP).encode("utf-8")


async def make_demo_stream(job_id: str, jobs: JobRepository) -> AsyncIterator[bytes]:
    from asyncio import sleep

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
    for i, claim in enumerate(demo_claims, start=1):
        # keep the job alive while the user is connected
        await jobs.touch(job_id)
        yield ndjson_line({"type": "claim", "payload": claim})
        yield ndjson_line(
            {"type": "progress", "payload": {"processed": i, "total": total}}
        )
        await sleep(0.35)

    yield ndjson_line({"type": "done"})
