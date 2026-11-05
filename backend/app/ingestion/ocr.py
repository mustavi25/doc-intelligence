from dataclasses import dataclass
from functools import lru_cache
import numpy as np
from app.config import settings

@dataclass
class OcrResult:
    text: str
    confidence: float
    engine: str

@lru_cache(maxsize=1)
def _rapid_engine():
    from rapidocr_onnxruntime import RapidOCR
    return RapidOCR()

def _rapid(img: np.ndarray) -> OcrResult:
    result, _ = _rapid_engine()(img)
    if not result:
        return OcrResult("", 0.0, "rapidocr")
    # sort lines top-to-bottom, then left-to-right
    result = sorted(result, key=lambda r: (round(r[0][0][1] / 12), r[0][0][0]))
    text = "\n".join(r[1] for r in result)
    conf = sum(float(r[2]) for r in result) / len(result)
    return OcrResult(text, conf, "rapidocr")

def _tesseract(img: np.ndarray) -> OcrResult:
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    confs = [int(c) for w, c in zip(data["text"], data["conf"]) if w.strip() and int(c) >= 0]
    text = pytesseract.image_to_string(img)
    return OcrResult(text, (sum(confs) / len(confs) / 100) if confs else 0.0, "tesseract")

def run_ocr(img: np.ndarray, engine: str | None = None) -> OcrResult:
    engine = engine or settings.ocr_engine
    if engine == "tesseract":
        return _tesseract(img)
    if engine == "rapidocr":
        return _rapid(img)
    try:
        return _rapid(img)
    except Exception:
        return _tesseract(img)