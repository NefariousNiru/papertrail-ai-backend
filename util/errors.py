# util/errors.py
from fastapi import HTTPException, status


class AppError(HTTPException):
    # Flow: raise AppError to short-circuit with a typed status & message.
    def __init__(
        self, message: str, http_status: int = status.HTTP_400_BAD_REQUEST
    ) -> None:
        super().__init__(status_code=http_status, detail=message)
