# model/api.py
from pydantic import BaseModel, Field
from model.claim import Verdict, Evidence


class ValidateKeyRequest(BaseModel):
    apiKey: str = Field(min_length=1)


class ValidateKeyResponse(BaseModel):
    ok: bool


class UploadPaperResponse(BaseModel):
    jobId: str


class StreamClaimsRequest(BaseModel):
    jobId: str
    apiKey: str


class VerifyClaimResponse(BaseModel):
    claimId: str
    verdict: Verdict
    confidence: float
    reasoningMd: str
    evidence: list[Evidence] | None = None
