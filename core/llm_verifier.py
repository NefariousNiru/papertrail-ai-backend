# core/llm_verifier.py
import json
from typing import Sequence
import httpx
from config.settings import settings
from core.entities import VerifyResult
import logging
from util.timing import timed

logger = logging.getLogger(__name__)


def _user_prompt(claim: str, packed_evidence: Sequence[str]) -> str:
    """
    Build the user message for verification with claim + concatenated excerpts.
    """
    joined = "\n\n---\n\n".join(packed_evidence) if packed_evidence else "(no evidence)"
    return f"CLAIM:\n{claim}\n\nEVIDENCE EXCERPTS:\n{joined}\n\nReturn JSON only."


async def anthropic_verify(
    *,
    api_key: str,
    model: str,
    claim: str,
    packed_evidence: Sequence[str],
    api_url: str,
    http_timeout: float = 45.0,
) -> VerifyResult:
    """
    Call Anthropic to judge support for a claim given retrieved excerpts. Returns a normalized VerifyResult.
    """
    headers = {
        "x-api-key": api_key,
        "anthropic-version": settings.ANTHROPIC_VERSION,
        "content-type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": 400,
        "system": settings.VERIFY_SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": _user_prompt(claim, packed_evidence)}],
        "temperature": 0.0,
    }
    with timed(logger, "ai.verify", model=model, k=len(packed_evidence)):
        async with httpx.AsyncClient(timeout=http_timeout) as client:
            resp = await client.post(api_url, headers=headers, json=payload)
            resp.raise_for_status()
            try:
                data = resp.json()
            except Exception:
                data = {}

    text = ""
    try:
        content = data.get("content") or []
        if content and isinstance(content, list):
            node = content[0]
            if isinstance(node, dict) and node.get("type") == "text":
                text = node.get("text") or ""
    except Exception:
        text = ""

    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:].strip()

    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = {
            "verdict": "unsupported",
            "confidence": 0.5,
            "reasoningMd": "Unable to parse verifier output.",
        }

    verdict = str(parsed.get("verdict", "unsupported")).lower()
    if verdict not in {"supported", "partially_supported", "unsupported"}:
        verdict = "unsupported"

    try:
        conf = float(parsed.get("confidence", 0.5))
    except Exception:
        conf = 0.5

    reasoning_md = str(parsed.get("reasoningMd", "")).strip()
    logger.info("ai.verify.result verdict=%s conf=%.2f", verdict, conf)

    return VerifyResult(
        verdict=verdict,
        confidence=max(0.0, min(1.0, conf)),
        reasoning_md=reasoning_md,
        evidence=[],
    )
