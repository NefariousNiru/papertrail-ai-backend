# service/api_key_validation_service.py
import httpx
from fastapi import status
from config.settings import settings
from util.enums import ErrorMessage
from util.errors import AppError
import logging

logger = logging.getLogger(__name__)


class ApiKeyValidationService:
    """
    Service to validate user entered a valid API Key
    """

    def __init__(self) -> None:
        self._url: str = settings.ANTHROPIC_API_URL
        self._model: str = settings.ANTHROPIC_MODEL

    async def validate_key(self, api_key: str) -> None:
        payload = {
            "model": self._model,
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "Ping"}],
        }
        timeout = httpx.Timeout(10.0, connect=5.0)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                res = await client.post(
                    self._url,
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json=payload,
                )
        except httpx.RequestError as e:
            logger.error("api.key.request_error err=%s", type(e).__name__)
            raise AppError(
                ErrorMessage.INTERNAL_ERROR.value.message,
                ErrorMessage.INTERNAL_ERROR.value.http_status,
            )

        if res.status_code // 100 == 2:
            logger.info("api.key.validated model=%s", self._model)
            return

        if res.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN):
            logger.warning("api.key.invalid status=%d", res.status_code)
            raise AppError(
                ErrorMessage.INVALID_API_KEY.value.message,
                ErrorMessage.INVALID_API_KEY.value.http_status,
            )

        logger.error("api.key.unexpected status=%d", res.status_code)
        raise AppError(
            ErrorMessage.INTERNAL_ERROR.value.message,
            ErrorMessage.INTERNAL_ERROR.value.http_status,
        )
