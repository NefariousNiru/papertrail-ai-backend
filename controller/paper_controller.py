# controller/paper_controller.py
from fastapi import APIRouter, File, Form, UploadFile, status, Depends
from fastapi.responses import StreamingResponse
from service.paper_service import PaperService
from model.api import UploadPaperResponse, StreamClaimsRequest, VerifyClaimResponse
from util.constants import InternalURIs
from util.deps import get_paper_service

paper_router = APIRouter()


@paper_router.post(
    InternalURIs.UPLOAD_PAPER,
    response_model=UploadPaperResponse,
    status_code=status.HTTP_201_CREATED,
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
    generator = service.stream_claims(payload.jobId)
    return StreamingResponse(generator, media_type="application/x-ndjson")


@paper_router.post(InternalURIs.VERIFY_CLAIM, response_model=VerifyClaimResponse)
async def verify_claim(
    claimId: str = Form(...),
    file: UploadFile = File(...),
    apiKey: str = Form(...),
    service: PaperService = Depends(get_paper_service),
):
    return await service.verify_claim(claim_id=claimId, file=file)
