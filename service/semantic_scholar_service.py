# service/semantic_scholar_service.py
import httpx, logging
from fastapi import status
from config.settings import settings
from util.errors import AppError

logger = logging.getLogger(__name__)


class SemanticScholarService:
    async def suggest(self, query: str, limit: int = 3):
        # TODO the query needs to have keywords not Natural Langauge
        params = {"query": query, "limit": limit, "fields": "title,authors,year,url"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(settings.SEMANTIC_SEARCH_URL, params=params)
        except httpx.RequestError as e:
            logger.error("semantic.request_error err=%s", e)
            raise AppError("Upstream request failed", status.HTTP_502_BAD_GATEWAY)

        print(res.json())
        if res.status_code != 200:
            logger.error("semantic.bad_status %d", res.status_code)
            raise AppError("Semantic Scholar error", status.HTTP_502_BAD_GATEWAY)

        data = res.json().get("data", [])
        return [
            {
                "title": p.get("title"),
                "authors": ", ".join(a["name"] for a in p.get("authors", [])[:3]),
                "year": p.get("year"),
                "url": p.get("url"),
            }
            for p in data
        ]
