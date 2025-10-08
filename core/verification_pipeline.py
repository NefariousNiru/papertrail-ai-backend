# core/verification_pipeline.py
from typing import List, Sequence
from config.settings import settings
from core.embeddings_retriever import build_index, top_k
from core.llm_verifier import VerifyResult, anthropic_verify
from core.pdf_text import extract_pdf_chunks
from core.entities import PdfChunk
from util import functions
import logging
from util.timing import timed

logger = logging.getLogger(__name__)


def _pack_for_prompt(chunks: Sequence[PdfChunk]) -> List[str]:
    """
    Convert chunks into compact prompt-ready excerpts with page tags.
    """
    out: List[str] = []
    for ch in chunks:
        if not ch.text.strip():
            continue
        out.append(f"[page {ch.page}]\n{functions.clip_words(ch.text, max_words=140)}")
    return out


def _evidence_for_api(chunks: Sequence[PdfChunk]) -> List[dict]:
    """
    Convert chunks into API-facing evidence items with limited excerpt length.
    """
    return [
        {
            "paperTitle": None,
            "page": ch.page,
            "section": ch.section,
            "paragraph": ch.paragraph,
            "excerpt": functions.clip_words(ch.text, max_words=100),
        }
        for ch in chunks
        if ch.text.strip()
    ]


async def verify_claim_against_pdf(
    *,
    claim_text: str,
    source_pdf_bytes: bytes,
    api_key: str,
    k: int = 4,
) -> tuple[VerifyResult, List[dict]]:
    """
    End-to-end verification:
    1) Parse PDF into chunks
    2) Embed locally
    3) Retrieve top-k relevant chunks
    4) Ask LLM to judge support
    Returns (VerifyResult, evidence_items_for_api).
    """
    # 1) parse
    with timed(logger, "verify.pipeline"):
        with timed(logger, "verify.parse"):
            chunks = (
                extract_pdf_chunks(source_pdf_bytes, max_chars_per_chunk=1400) or []
            )
        texts = [c.text for c in chunks] or [""]

        with timed(logger, "verify.embed", n=len(texts)):
            index = build_index(texts)

        with timed(logger, "verify.retrieve", k=min(k, len(texts))):
            hits = top_k(index, query=claim_text, k=min(k, len(texts)))
            top = [chunks[i] for i, _ in hits] if chunks else []
        logger.info("verify.retrieve.top count=%d", len(top))

        packed = _pack_for_prompt(top)
        v = await anthropic_verify(
            api_key=api_key,
            model=settings.ANTHROPIC_MODEL,
            claim=claim_text,
            packed_evidence=packed,
            api_url=settings.ANTHROPIC_API_URL,
        )

    return v, _evidence_for_api(top)
