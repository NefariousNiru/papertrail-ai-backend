# core/entities.py
from dataclasses import dataclass
from typing import Optional, List
import numpy as np


@dataclass
class EmbeddingIndex:
    """
    L2-normalized embedding matrix for cosine similarity search.
    """

    embeddings: np.ndarray  # (n, d) float32


@dataclass
class EvidenceItem:
    page: Optional[int]
    section: Optional[str]
    paragraph: Optional[int]
    excerpt: str


@dataclass
class VerifyResult:
    verdict: str
    confidence: float
    reasoning_md: str
    evidence: List[EvidenceItem]


@dataclass
class PdfChunk:
    page: int  # 1-based page index
    section: Optional[str]  # unknown for MVP
    paragraph: Optional[int]  # chunk ordinal within page
    text: str
