# controller/semantic_search_controller.py
from fastapi import APIRouter, Body, Depends
from service.semantic_scholar_service import SemanticScholarService
from util.constants import InternalURIs

semantic_search_router = APIRouter()

@semantic_search_router.post(InternalURIs.SUGGEST_CITATIONS)
async def suggest_citations(
    payload: dict = Body(...),
    svc: SemanticScholarService = Depends(SemanticScholarService),
):
    query = payload.get("claimText")
    print(query)
    return {"suggestions": await svc.suggest(query)}
