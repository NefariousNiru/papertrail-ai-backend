# core/embeddings_retriever.py
from functools import lru_cache
from typing import List, Sequence, Tuple
import numpy as np
from sentence_transformers import SentenceTransformer
from config.settings import settings
from core.entities import EmbeddingIndex


@lru_cache(maxsize=1)
def _load_model() -> SentenceTransformer:
    """
    Lazy-load the sentence embedding model.

    Model is kept CPU-friendly; adjust in settings if you want a larger model.
    """
    name = settings.EMBEDDING_MODEL_NAME
    return SentenceTransformer(name, device="cpu")


def build_index(texts: Sequence[str], batch_size: int = 64) -> EmbeddingIndex:
    """
    Encode `texts` into an EmbeddingIndex with L2-normalized vectors.
    """
    model = _load_model()
    vecs = model.encode(
        list(texts),
        batch_size=batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    emb = vecs.astype(np.float32, copy=False)
    return EmbeddingIndex(embeddings=emb)


def top_k(index: EmbeddingIndex, query: str, k: int = 4) -> List[Tuple[int, float]]:
    """
    Return top-k (index, cosine_sim) for the query against the index.
    """
    model = _load_model()
    q = model.encode([query], convert_to_numpy=True, normalize_embeddings=True).astype(
        np.float32, copy=False
    )[0]
    sims = (index.embeddings @ q).astype(float)  # cosine due to normalization
    k = max(1, min(k, sims.shape[0]))
    top_idx = np.argpartition(sims, -k)[-k:]
    return sorted(
        ((int(i), float(sims[int(i)])) for i in top_idx),
        key=lambda t: t[1],
        reverse=True,
    )
