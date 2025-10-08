# core/pdf_text.py
from typing import List, Tuple
import fitz
from core.entities import PdfChunk


def extract_pages_texts(file_bytes: bytes) -> List[Tuple[int, str]]:
    """
    Return [(page_number, page_text)] for the whole PDF.
    If PyMuPDF is unavailable or parsing fails, returns [].
    """
    try:
        out: List[Tuple[int, str]] = []
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            for i in range(doc.page_count):
                page = doc.load_page(i)
                txt = (page.get_text("text") or "").strip()
                out.append((i + 1, txt))
        return out
    except Exception:
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
    for pg, txt in pages:
        parts = _greedy_para_split(txt, max_chars_per_chunk)
        if not parts:
            continue
        for j, chunk in enumerate(parts, start=1):
            out.append(PdfChunk(page=pg, section=None, paragraph=j, text=chunk))
    return out or [PdfChunk(page=1, section=None, paragraph=None, text="")]
