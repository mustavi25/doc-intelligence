from functools import lru_cache
import numpy as np
from app.config import settings
from app.db.mongo import db


@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(settings.embedding_model)


def embed(texts: list[str]) -> np.ndarray:
    return _model().encode(texts, normalize_embeddings=True)


def chunk_text(text: str, size: int = 800, overlap: int = 100) -> list[str]:
    text = text.strip()
    if not text:
        return []
    out, i = [], 0
    while i < len(text):
        out.append(text[i:i + size])
        i += size - overlap
    return out


def index_document(doc_id, pages) -> int:
    db.chunks.delete_many({"document_id": doc_id})
    rows = []
    for p in pages:
        for n, c in enumerate(chunk_text(p.text)):
            rows.append({"document_id": doc_id, "page_no": p.page_no, "chunk_no": n, "text": c})
    if not rows:
        return 0
    vecs = embed([r["text"] for r in rows])
    for r, v in zip(rows, vecs):
        r["embedding"] = v.tolist()
    db.chunks.insert_many(rows)
    return len(rows)


def search(query: str, allowed_ids: set | None = None, limit: int = 20) -> list[dict]:
    q = {"document_id": {"$in": list(allowed_ids)}} if allowed_ids is not None else {}
    chunks = list(db.chunks.find(q, {"document_id": 1, "page_no": 1, "text": 1, "embedding": 1}))
    if not chunks:
        return []
    matrix = np.array([c["embedding"] for c in chunks], dtype=np.float32)
    scores = matrix @ embed([query])[0]
    best = {}
    for c, s in zip(chunks, scores):
        d = c["document_id"]
        if d not in best or s > best[d]["score"]:
            best[d] = {"document_id": d, "score": float(s), "page_no": c["page_no"], "snippet": c["text"][:200]}
    return sorted(best.values(), key=lambda x: -x["score"])[:limit]