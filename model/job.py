# model/job.py
from typing import Literal
from pydantic import BaseModel

JobStatus = Literal[
    "pending",
    "processing",
    "streaming",
    "finished",
    "failed",
]


class Job(BaseModel):
    id: str
    status: JobStatus
    processed: int = 0
    total: int = 0
