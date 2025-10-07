# controller/controller_dependencies.py
from repository.claim_buffer_repository import ClaimBufferRepository
from repository.verification_repository import VerificationRepository
from service.paper_service import PaperService
from repository.job_repository import JobRepository


def get_paper_service() -> PaperService:
    _jobs = JobRepository()
    _buffer = ClaimBufferRepository()
    _verifications = VerificationRepository()
    _service = PaperService(_jobs, _buffer, _verifications)
    return _service
