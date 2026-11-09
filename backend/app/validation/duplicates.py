import re
from rapidfuzz import fuzz
from app.db.mongo import db
from app.validation.rules import issue

FUZZY_THRESHOLD = 90


def find_duplicates(doc_id, data: dict, file_duplicate_of=None) -> list[dict]:
    out = []
    if file_duplicate_of:
        out.append(issue("duplicate_file", "warning", None,
                         f"Identical file already uploaded (document {file_duplicate_of})"))
    inv, sup, total = data.get("invoice_number"), data.get("supplier_name"), data.get("total")
    if not inv or not sup:
        return out

    # exact: same supplier + invoice number + total
    exact = db.extractions.find({
        "document_id": {"$ne": doc_id},
        "data.invoice_number": {"$regex": f"^{re.escape(inv)}$", "$options": "i"},
        "data.supplier_name": {"$regex": f"^{re.escape(sup)}$", "$options": "i"},
        "data.total": total,
    }, {"document_id": 1}).limit(5)
    seen = set()
    for e in exact:
        seen.add(e["document_id"])
        out.append(issue("duplicate_invoice", "error", "invoice_number",
                         f"Same supplier, invoice number and total as document {e['document_id']}"))

    # fuzzy: same total and date, similar supplier
    if total is not None and data.get("invoice_date"):
        cands = db.extractions.find({
            "document_id": {"$ne": doc_id, "$nin": list(seen)},
            "data.total": total, "data.invoice_date": data["invoice_date"],
        }, {"document_id": 1, "data.supplier_name": 1}).limit(20)
        for c in cands:
            s = c["data"].get("supplier_name") or ""
            if fuzz.token_sort_ratio(sup.lower(), s.lower()) >= FUZZY_THRESHOLD:
                out.append(issue("possible_duplicate", "warning", "supplier_name",
                                 f"Very similar to document {c['document_id']} (same date and total)"))
    return out