import re
from fastapi import APIRouter, Query
from app.db.mongo import db
from app.search import semantic

router = APIRouter(prefix="/api", tags=["search"])


def _allowed_ids(supplier, status, date_from, date_to, min_total, max_total):
    """Apply structured filters. Returns None when no filter is set."""
    ex_q, doc_q = {}, {}
    if supplier:
        ex_q["data.supplier_name"] = {"$regex": re.escape(supplier), "$options": "i"}
    if date_from or date_to:
        ex_q["data.invoice_date"] = {k: v for k, v in (("$gte", date_from), ("$lte", date_to)) if v}
    if min_total is not None or max_total is not None:
        ex_q["data.total"] = {k: v for k, v in (("$gte", min_total), ("$lte", max_total)) if v is not None}
    if status:
        doc_q["status"] = status
    if not ex_q and not doc_q:
        return None
    ids = None
    if ex_q:
        ids = {e["document_id"] for e in db.extractions.find(ex_q, {"document_id": 1})}
    if doc_q:
        d_ids = {d["_id"] for d in db.documents.find(doc_q, {"_id": 1})}
        ids = d_ids if ids is None else ids & d_ids
    return ids


def _keyword(q, allowed):
    hits = {}
    base = {"$text": {"$search": q}}
    if allowed is not None:
        base["document_id"] = {"$in": list(allowed)}
    for p in db.pages.find(base, {"score": {"$meta": "textScore"}, "document_id": 1, "page_no": 1, "text": 1}) \
                     .sort([("score", {"$meta": "textScore"})]).limit(100):
        d = p["document_id"]
        if d not in hits:
            hits[d] = {"document_id": d, "score": float(p["score"]), "page_no": p["page_no"],
                       "snippet": p["text"][:200]}
    # also match structured fields (invoice number, supplier, customer)
    rx = {"$regex": re.escape(q), "$options": "i"}
    fq = {"$or": [{"data.invoice_number": rx}, {"data.supplier_name": rx}, {"data.customer_name": rx}]}
    if allowed is not None:
        fq["document_id"] = {"$in": list(allowed)}
    for e in db.extractions.find(fq, {"document_id": 1}).limit(100):
        hits.setdefault(e["document_id"], {"document_id": e["document_id"], "score": 5.0,
                                           "page_no": None, "snippet": "Matched an extracted field"})
    return sorted(hits.values(), key=lambda x: -x["score"])


def _rrf(*lists, k=60):
    """Reciprocal rank fusion for hybrid mode."""
    scores, info = {}, {}
    for lst in lists:
        for rank, r in enumerate(lst):
            scores[r["document_id"]] = scores.get(r["document_id"], 0) + 1 / (k + rank + 1)
            info.setdefault(r["document_id"], r)
    return [{**info[d], "score": s} for d, s in sorted(scores.items(), key=lambda x: -x[1])]


@router.get("/search")
def search(q: str = "", mode: str = Query("keyword", pattern="^(keyword|semantic|hybrid)$"),
           supplier: str | None = None, status: str | None = None,
           date_from: str | None = None, date_to: str | None = None,
           min_total: float | None = None, max_total: float | None = None,
           limit: int = Query(20, le=100)):
    allowed = _allowed_ids(supplier, status, date_from, date_to, min_total, max_total)
    if not q.strip():                      # filters only
        ids = allowed if allowed is not None else {d["_id"] for d in db.documents.find({}, {"_id": 1}).limit(limit)}
        results = [{"document_id": i, "score": 0, "page_no": None, "snippet": ""} for i in list(ids)[:limit]]
    elif mode == "keyword":
        results = _keyword(q, allowed)
    elif mode == "semantic":
        results = semantic.search(q, allowed, limit)
    else:
        results = _rrf(_keyword(q, allowed), semantic.search(q, allowed, limit))
    results = results[:limit]

    out = []
    for r in results:
        doc = db.documents.find_one({"_id": r["document_id"]}, {"filename": 1, "status": 1, "file_type": 1})
        ex = db.extractions.find_one({"document_id": r["document_id"]}, {"data": 1})
        d = (ex or {}).get("data") or {}
        out.append({"id": str(r["document_id"]), "filename": (doc or {}).get("filename"),
                    "status": (doc or {}).get("status"), "score": round(r["score"], 4),
                    "page_no": r["page_no"], "snippet": r["snippet"],
                    "invoice_number": d.get("invoice_number"), "supplier_name": d.get("supplier_name"),
                    "total": d.get("total"), "invoice_date": d.get("invoice_date")})
    return {"query": q, "mode": mode, "count": len(out), "results": out}