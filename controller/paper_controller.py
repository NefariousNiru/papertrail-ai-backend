# controller/paper_controller.py
from fastapi import APIRouter, File, Form, UploadFile, status, Depends
from fastapi.responses import StreamingResponse
from fastapi_limiter.depends import RateLimiter
from config.settings import settings
from service.paper_service import PaperService
from model.api import UploadPaperResponse, StreamClaimsRequest, VerifyClaimResponse
from util.constants import InternalURIs
from controller.controller_dependencies import (
    get_paper_service,
    enforce_max_upload_size,
)

paper_router = APIRouter(
    dependencies=[
        Depends(
            RateLimiter(
                times=settings.RATE_LIMIT_TIMES, seconds=settings.RATE_LIMIT_SECONDS
            )
        )
    ]
)


@paper_router.post(
    InternalURIs.UPLOAD_PAPER,
    response_model=UploadPaperResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_max_upload_size)],
)
async def upload_paper(
    file: UploadFile = File(...),
    apiKey: str = Form(...),
    service: PaperService = Depends(get_paper_service),
) -> UploadPaperResponse:
    job_id = await service.create_job_for_file(file)
    return UploadPaperResponse(jobId=job_id)


@paper_router.post(InternalURIs.STREAM_CLAIM)
async def stream_claims(
    payload: StreamClaimsRequest,
    service: PaperService = Depends(get_paper_service),
):
    generator = service.stream_claims(payload.jobId, payload.apiKey)
    return StreamingResponse(generator, media_type="application/x-ndjson")


@paper_router.post(
    InternalURIs.VERIFY_CLAIM,
    response_model=VerifyClaimResponse,
    dependencies=[Depends(enforce_max_upload_size)],
)
async def verify_claim(
    jobId: str = Form(...),
    claimId: str = Form(...),
    file: UploadFile = File(...),
    apiKey: str = Form(...),
    service: PaperService = Depends(get_paper_service),
):
    return await service.verify_claim(
        claim_id=claimId, file=file, job_id=jobId, api_key=apiKey
    )
