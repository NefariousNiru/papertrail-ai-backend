# util/deps.py
from repository.claim_buffer_repository import ClaimBufferRepository
from service.paper_service import PaperService
from repository.job_repository import JobRepository


def get_paper_service() -> PaperService:
    _jobs = JobRepository()
    _buffer = ClaimBufferRepository()
    _service = PaperService(_jobs, _buffer)
    return _service
