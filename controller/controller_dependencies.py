# controller/controller_dependencies.py
from repository.blob_repository import BlobRepository
from repository.claim_buffer_repository import ClaimBufferRepository
from repository.verification_repository import VerificationRepository
from service.paper_service import PaperService
from repository.job_repository import JobRepository
from fastapi import File, HTTPException, Request, UploadFile
from config.settings import settings


def get_paper_service() -> PaperService:
    _jobs = JobRepository()
    _buffer = ClaimBufferRepository()
    _verifications = VerificationRepository()
    _blobs = BlobRepository()
    _service = PaperService(_jobs, _buffer, _verifications, _blobs)
    return _service


async def enforce_max_upload_size(
    request: Request, file: UploadFile = File(...)
) -> UploadFile:
    # Fast pre-check via Content-Length if present
    MAX_BYTES = settings.MAX_FILE_MB * 1024 * 1024
    cl = request.headers.get("content-length")
    if cl and int(cl) > MAX_BYTES:
        # JSON envelope for 413
        raise HTTPException(
            status_code=413,
            detail={
                "ok": False,
                "error": "file_too_large",
                "maxMb": settings.MAX_FILE_MB,
            },
        )

    # Hard cap while reading initial bytes (works even if no Content-Length)
    blob = await file.read(MAX_BYTES + 1)
    if len(blob) > MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail={
                "ok": False,
                "error": "file_too_large",
                "maxMb": settings.MAX_FILE_MB,
            },
        )

    # Reset so downstream can re-read file stream
    await file.seek(0)
    return file
