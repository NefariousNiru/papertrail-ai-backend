# util/types.py
from typing import Literal, TypedDict


# Flow: Narrow types for NDJSON events.
EventType = Literal["claim", "progress", "done", "error"]


class ProgressPayload(TypedDict):
    processed: int
    total: int


class ErrorPayload(TypedDict, total=False):
    message: str
