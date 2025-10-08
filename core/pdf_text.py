# core/pdf_text.py
from typing import List, Tuple
import fitz
from core.entities import PdfChunk
from util.timing import timed
import logging

logger = logging.getLogger(__name__)


def extract_pages_texts(file_bytes: bytes) -> List[Tuple[int, str]]:
    """
    Return [(page_number, page_text)] for the whole PDF.
    If PyMuPDF is unavailable or parsing fails, returns [].
    """
    try:
        out: List[Tuple[int, str]] = []
        with timed(logger, "pdf.open"):
            with fitz.open(stream=file_bytes, filetype="pdf") as doc:
                pages = doc.page_count
                with timed(logger, "pdf.parse", pages=pages):
                    for i in range(pages):
                        page = doc.load_page(i)
                        txt = (page.get_text("text") or "").strip()
                        out.append((i + 1, txt))
        logger.info("pdf.pages count=%d", len(out))
        return out
    except Exception:
        # do not log payloads
        logger.error("pdf.parse.error", exc_info=True)
        return []


def _greedy_para_split(text: str, max_chars: int = 1400) -> List[str]:
    paras = [p.strip() for p in text.split("\n") if p.strip()]
    if not paras:
        return []
    chunks: List[str] = []
    buf: List[str] = []
    size = 0
    for p in paras:
        if size + len(p) + 1 > max_chars and buf:
            chunks.append("\n".join(buf))
            buf = [p]
            size = len(p)
        else:
            buf.append(p)
            size += len(p) + 1
    if buf:
        chunks.append("\n".join(buf))
    return chunks


def extract_pdf_chunks(
    file_bytes: bytes, max_chars_per_chunk: int = 1400
) -> List[PdfChunk]:
    """
    Page-aware chunking. Chunks are paragraph groups (~max_chars).
    """
    pages = extract_pages_texts(file_bytes)
    if not pages:
        return [PdfChunk(page=1, section=None, paragraph=None, text="")]
    out: List[PdfChunk] = []
    with timed(logger, "pdf.chunk", pages=len(pages), max_chars=max_chars_per_chunk):
        for pg, txt in pages:
            parts = _greedy_para_split(txt, max_chars_per_chunk)
            if not parts:
                continue
            for j, chunk in enumerate(parts, start=1):
                out.append(PdfChunk(page=pg, section=None, paragraph=j, text=chunk))
    logger.info("pdf.chunks count=%d", len(out))
    return out or [PdfChunk(page=1, section=None, paragraph=None, text="")]
