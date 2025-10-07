# model/claim.py
from enum import Enum
from pydantic import BaseModel


class ClaimStatus(str, Enum):
    cited = "cited"
    uncited = "uncited"
    weakly_cited = "weakly_cited"


class Verdict(str, Enum):
    supported = "supported"
    partially_supported = "partially_supported"
    unsupported = "unsupported"
    skipped = "skipped"


class Suggestion(BaseModel):
    title: str
    url: str
    venue: str | None = None
    year: int | None = None


class Claim(BaseModel):
    id: str
    text: str
    status: ClaimStatus
    verdict: Verdict | None = None
    confidence: float | None = None
    reasoningMd: str | None = None
    suggestions: list[Suggestion] | None = None
    sourceUploaded: bool = False
