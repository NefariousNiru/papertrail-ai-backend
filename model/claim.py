# model/claim.py
from enum import Enum
from pydantic import BaseModel, field_validator


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


class Evidence(BaseModel):
    paperTitle: str | None = None
    page: int | None = None
    section: str | None = None
    paragraph: int | None = None
    excerpt: str | None = None

    # Safety net: enforce 100-word cap even if service forgets to trim
    @classmethod
    @field_validator("excerpt")
    def _cap_excerpt(cls, v: str | None) -> str | None:
        if v is None:
            return v
        words = v.split()
        return v if len(words) <= 100 else " ".join(words[:100]) + " …"


class Claim(BaseModel):
    id: str
    text: str
    status: ClaimStatus
    verdict: Verdict | None = None
    confidence: float | None = None
    reasoningMd: str | None = None
    suggestions: list[Suggestion] | None = None
    sourceUploaded: bool = False
    evidence: list[Evidence] | None = None
