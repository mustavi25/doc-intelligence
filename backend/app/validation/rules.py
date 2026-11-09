from datetime import date, datetime
from decimal import Decimal, InvalidOperation

TOL = Decimal("0.01")
REQUIRED_ERR = ["invoice_number", "invoice_date", "supplier_name", "total"]
REQUIRED_WARN = ["customer_name", "currency", "subtotal", "tax"]
KNOWN_CURRENCIES = {"USD", "EUR", "GBP", "INR", "BDT", "AUD", "CAD", "JPY", "CNY", "AED", "SGD", "CHF", "SAR", "MYR"}


def D(v):
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None


def issue(rule, severity, field, message):
    return {"rule": rule, "severity": severity, "field": field, "message": message, "resolved": False}


def close(a: Decimal, b: Decimal) -> bool:
    return abs(a - b) <= TOL


def validate(data: dict, field_confidence: dict | None = None, uncertain: list | None = None) -> list[dict]:
    out = []

    # 1. missing fields
    for f in REQUIRED_ERR:
        if data.get(f) in (None, ""):
            out.append(issue("missing_field", "error", f, f"Required field '{f}' is missing"))
    for f in REQUIRED_WARN:
        if data.get(f) in (None, ""):
            out.append(issue("missing_field", "warning", f, f"Field '{f}' is missing"))

    # 2. numeric sanity
    nums = {f: D(data.get(f)) for f in ("subtotal", "tax", "total")}
    for f, v in nums.items():
        if data.get(f) is not None and v is None:
            out.append(issue("invalid_number", "error", f, f"'{f}' is not a valid number"))
        elif v is not None and v < 0:
            out.append(issue("negative_value", "error", f, f"'{f}' is negative ({v})"))
    sub, tax, total = nums["subtotal"], nums["tax"], nums["total"]

    # 3. subtotal + tax = total
    if sub is not None and tax is not None and total is not None:
        if not close(sub + tax, total):
            out.append(issue("total_mismatch", "error", "total",
                             f"subtotal {sub} + tax {tax} = {sub + tax}, but total is {total}"))
    elif sub is not None and total is not None and tax is None and not close(sub, total):
        out.append(issue("total_mismatch", "warning", "total",
                         f"total {total} differs from subtotal {sub} and no tax was found"))

    # 4. line items
    items = data.get("line_items") or []
    amounts = []
    for i, it in enumerate(items, start=1):
        qty, price, amt = D(it.get("quantity")), D(it.get("unit_price")), D(it.get("amount"))
        if amt is not None:
            amounts.append(amt)
        if it.get("_ungrounded"):
            out.append(issue("ungrounded_value", "warning", f"line_items[{i}]",
                             f"Line {i} amount was not found in the source text"))
        if qty is not None and price is not None and amt is not None and not close(qty * price, amt):
            out.append(issue("line_math", "error", f"line_items[{i}]",
                             f"Line {i}: {qty} x {price} = {qty * price}, but amount is {amt}"))
    if amounts:
        s = sum(amounts)
        ref, name = (sub, "subtotal") if sub is not None else (total, "total")
        if ref is not None and not close(s, ref):
            out.append(issue("items_sum_mismatch", "error", "line_items",
                             f"Line items sum to {s}, but {name} is {ref}"))

    # 5. date sanity
    d = data.get("invoice_date")
    if d:
        try:
            dt = datetime.strptime(d, "%Y-%m-%d").date()
            if dt > date.today():
                out.append(issue("future_date", "warning", "invoice_date", f"Invoice date {d} is in the future"))
            elif dt.year < 2000:
                out.append(issue("implausible_date", "warning", "invoice_date", f"Invoice date {d} is implausibly old"))
        except ValueError:
            out.append(issue("invalid_date", "error", "invoice_date", f"'{d}' is not a valid YYYY-MM-DD date"))

    # 6. currency
    cur = data.get("currency")
    if cur and cur.upper() not in KNOWN_CURRENCIES:
        out.append(issue("unknown_currency", "warning", "currency", f"Unrecognised currency '{cur}'"))

    # 7. grounding / uncertainty from the extractor
    for f, c in (field_confidence or {}).items():
        if c == 0.0:
            out.append(issue("ungrounded_value", "warning", f,
                             f"The model returned a value for '{f}' that is not in the document, so it was removed"))
    for f in uncertain or []:
        out.append(issue("uncertain_field", "warning", f, f"The model is not confident about '{f}'"))
    return out