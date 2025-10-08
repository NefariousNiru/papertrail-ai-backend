# core/anthropic_client.py
import json
from typing import Dict, Any
import httpx
from config.settings import settings
import logging
from util.timing import timed

logger = logging.getLogger(__name__)


async def _post_json(
    url: str, headers: Dict[str, str], payload: Dict[str, Any], timeout: float = 60.0
) -> Dict[str, Any]:
    """
    Make a JSON POST to `url`. Raises for non-2xx. Returns parsed JSON dict or {} on parse failure.
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        try:
            return r.json()
        except Exception:
            return {}


def _extract_user(page_number: int, page_text: str) -> str:
    """
    Build the user message for extraction with page-number context.
    """
    return f"Page {page_number} text:\n{page_text}\n\nReturn claim objects as NDJSON lines."


def _parse_ndjson(raw: str) -> list[dict]:
    out: list[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        # ignore code fences if any sneak in
        if line.startswith("```"):
            continue
        try:
            obj = json.loads(line)
            txt = str(obj.get("text") or "").strip()
            if not txt:
                continue
            cid = str(obj.get("id") or "").strip()
            status = str(obj.get("status") or "uncited").strip()
            out.append({"id": cid or "", "text": txt, "status": status})
        except Exception:
            # drop malformed trailing line (common when outputs truncate)
            continue
    return out


async def extract_claims_from_page(
    *,
    api_key: str,
    model: str,
    api_url: str,
    page_number: int,
    page_text: str,
    timeout: float = 45.0,
) -> list[dict]:
    """
    Call Anthropic to extract claims for a single page and return a normalized list of claim dicts.
    """
    headers = {
        "x-api-key": api_key,
        "anthropic-version": settings.ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": 800,
        "system": settings.EXTRACT_SYSTEM_PROMPT,
        "messages": [
            {"role": "user", "content": _extract_user(page_number, page_text)}
        ],
        "temperature": 0.0,
    }
    with timed(logger, "ai.extract", page=page_number, model=model):
        data = await _post_json(api_url, headers, payload, timeout=timeout)

    text = ""
    try:
        content = data.get("content") or []
        if content and isinstance(content, list):
            node = content[0]
            if isinstance(node, dict) and node.get("type") == "text":
                text = node.get("text") or ""
    except Exception:
        text = ""

    claims = _parse_ndjson(text)
    ready: list[dict] = []
    for i, c in enumerate(claims, start=1):
        ready.append(
            {
                "id": c["id"] or f"p{page_number}_{i}",
                "text": c["text"],
                "status": c.get("status") or "uncited",
            }
        )
    logger.info("ai.extract.claims page=%d count=%d", page_number, len(ready))
    return ready
