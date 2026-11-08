import anthropic
from app.config import settings
from app.extraction.schema import INVOICE_TOOL
from app.extraction.prompts import SYSTEM_PROMPT, PROMPT_VERSION
from app.extraction.grounding import ground

MAX_CHARS = 30_000

def extract_invoice(text: str) -> dict:
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=60, max_retries=3)
    resp = client.messages.create(
        model=settings.extraction_model,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        tools=[INVOICE_TOOL],
        tool_choice={"type": "tool", "name": "record_invoice"},
        messages=[{"role": "user", "content": f"<document>\n{text[:MAX_CHARS]}\n</document>"}],
    )
    raw = next(b.input for b in resp.content if b.type == "tool_use")
    clean, conf = ground(raw, text)
    return {"data": clean, "raw": raw, "field_confidence": conf,
            "model": settings.extraction_model, "prompt_version": PROMPT_VERSION,
            "usage": {"in": resp.usage.input_tokens, "out": resp.usage.output_tokens}}