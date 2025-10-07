# controller/validation_controller.py
from fastapi import APIRouter, status
from fastapi.params import Depends
from model.api import ValidateKeyResponse, ValidateKeyRequest
from service.api_key_validation_service import ApiKeyValidationService
from util.constants import InternalURIs

validation_router = APIRouter()


@validation_router.post(
    InternalURIs.VALIDATE_API_KEY,
    response_model=ValidateKeyResponse,
    status_code=status.HTTP_200_OK,
)
async def validate_api_key(
    payload: ValidateKeyRequest,
    service: ApiKeyValidationService = Depends(ApiKeyValidationService),
) -> ValidateKeyResponse:
    await service.validate_key(payload.apiKey)
    return ValidateKeyResponse(ok=True)
