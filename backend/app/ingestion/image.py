import numpy as np
import cv2
from PIL import Image, ImageSequence
from app.ingestion.types import PageResult
from app.ingestion.ocr import run_ocr

class ImageError(Exception):
    pass

def preprocess(img: np.ndarray) -> np.ndarray:
    """Light cleanup: upscale small images and denoise. Keep colour for RapidOCR."""
    h, w = img.shape[:2]
    if max(h, w) < 1200:
        scale = 1600 / max(h, w)
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    return cv2.fastNlMeansDenoisingColored(img, None, 5, 5, 7, 21)

def iter_image_pages(path: str):
    try:
        im = Image.open(path)
        im.load()
    except Exception as e:
        raise ImageError(f"Corrupted or unreadable image: {e}")
    for n, frame in enumerate(ImageSequence.Iterator(im), start=1):   # TIFF multi-frame
        try:
            arr = np.array(frame.convert("RGB"))
            r = run_ocr(preprocess(arr))
            yield PageResult(n, r.text, "ocr", r.confidence, meta={"engine": r.engine})
        except Exception as e:
            yield PageResult(n, "", "error", error=str(e))