import fitz
import numpy as np
from app.ingestion.types import PageResult
from app.ingestion.ocr import run_ocr

MIN_CHARS = 30

class PdfError(Exception):
    pass

def count_pages(path: str) -> int:
    try:
        with fitz.open(path) as doc:
            if doc.needs_pass:
                raise PdfError("PDF is password protected")
            return doc.page_count
    except PdfError:
        raise
    except Exception as e:
        raise PdfError(f"Corrupted or unreadable PDF: {e}")

def iter_pdf_pages(path: str):
    """Yields one PageResult per page. A bad page never kills the whole file."""
    doc = fitz.open(path)
    try:
        for i in range(doc.page_count):
            try:
                page = doc[i]
                text = page.get_text("text").strip()
                if len(text) >= MIN_CHARS:
                    yield PageResult(i + 1, text, "digital")
                    continue
                pix = page.get_pixmap(dpi=300, alpha=False)
                img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
                r = run_ocr(img)
                yield PageResult(i + 1, r.text, "ocr", r.confidence, meta={"engine": r.engine})
            except Exception as e:
                yield PageResult(i + 1, "", "error", error=str(e))
    finally:
        doc.close()