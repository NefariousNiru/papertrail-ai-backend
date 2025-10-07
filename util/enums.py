# util/enums.py
from enum import Enum
from typing import NamedTuple
from fastapi import status


class Color(str, Enum):
    RESET = "\033[0m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    BOLD = "\033[1m"

    def __str__(self):
        return self.value


class Environment(str, Enum):
    DEV = "dev"
    PROD = "prod"


class ErrorInfo(NamedTuple):
    message: str
    http_status: int


class ErrorMessage(Enum):
    INVALID_API_KEY = ErrorInfo("Invalid API Key", status.HTTP_401_UNAUTHORIZED)
    INTERNAL_ERROR = ErrorInfo("Internal Error", status.HTTP_502_BAD_GATEWAY)
