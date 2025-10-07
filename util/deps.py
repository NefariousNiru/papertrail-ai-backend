# util/deps.py
from service.paper_service import PaperService
from repository.job_repository import JobRepository


def get_paper_service() -> PaperService:
    _jobs = JobRepository()
    _service = PaperService(_jobs)
    return _service
