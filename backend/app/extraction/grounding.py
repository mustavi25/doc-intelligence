import re

def _norm(s: str) -> str:
    return re.sub(r"[\s,]+", "", str(s)).lower()

def _num_in_text(value: float, text: str) -> bool:
    for cand in (f"{value:.2f}", f"{value:g}", f"{int(value)}" if float(value).is_integer() else None):
        if cand and cand.replace(",", "") in text.replace(",", ""):
            return True
    return False

def ground(data: dict, text: str) -> tuple[dict, dict]:
    """Null out values not found in the source text. Returns (clean_data, confidence)."""
    nt = _norm(text)
    conf, out = {}, dict(data)
    for f in ("invoice_number", "invoice_date", "supplier_name", "customer_name", "currency"):
        v = out.get(f)
        if v is None:
            conf[f] = None
            continue
        snippet = (out.get("source_snippets") or {}).get(f, "")
        found = _norm(v) in nt or (snippet and _norm(snippet) in nt)
        if f == "invoice_date":       # normalized dates may not appear verbatim
            found = bool(snippet) and _norm(snippet) in nt
        if f == "currency":
            found = found or any(sym in text for sym in ("$", "€", "£", "₹", "৳"))
        conf[f] = 1.0 if found else 0.0
        if not found:
            out[f] = None
    for f in ("subtotal", "tax", "total"):
        v = out.get(f)
        if v is None:
            conf[f] = None
            continue
        ok = _num_in_text(v, text)
        conf[f] = 1.0 if ok else 0.0
        if not ok:
            out[f] = None
    items = []
    for it in out.get("line_items") or []:
        amt = it.get("amount")
        if amt is not None and not _num_in_text(amt, text):
            it = {**it, "amount": None, "_ungrounded": True}
        items.append(it)
    out["line_items"] = items
    return out, conf