import time, traceback
from datetime import datetime, timedelta, timezone
from pymongo import ReturnDocument
from app.db.mongo import db, init_indexes
from app.ingestion.file_router import detect_type
from app.ingestion import pdf, image, spreadsheet

LOW_CONF = 0.6

def now():
    return datetime.now(timezone.utc)

def claim_next():
    return db.documents.find_one_and_update(
        {"status": "queued"},
        {"$set": {"status": "processing", "started_at": now(), "heartbeat_at": now()},
         "$inc": {"attempts": 1}},
        sort=[("created_at", 1)], return_document=ReturnDocument.AFTER)

def recover_stale(minutes=10):
    db.documents.update_many(
        {"status": "processing", "heartbeat_at": {"$lt": now() - timedelta(minutes=minutes)}},
        {"$set": {"status": "queued"}})

def event(doc_id, stage, status, t0, error=None):
    db.processing_events.insert_one({
        "document_id": doc_id, "stage": stage, "status": status, "started_at": now(),
        "duration_ms": int((time.time() - t0) * 1000), "error": error})

def save_page(doc_id, p):
    db.pages.replace_one(
        {"document_id": doc_id, "page_no": p.page_no},
        {"document_id": doc_id, "page_no": p.page_no, "text": p.text, "source": p.source,
         "ocr_confidence": p.ocr_confidence, "error": p.error, "meta": p.meta},
        upsert=True)

def process(doc) -> str:
    doc_id, path = doc["_id"], doc["storage_path"]
    t0 = time.time()
    kind = detect_type(path, doc["filename"])
    db.documents.update_one({"_id": doc_id}, {"$set": {"file_type": kind}})
    if kind in ("empty", "unknown"):
        raise ValueError("Empty file" if kind == "empty" else "Unsupported or corrupted file")

    db.pages.delete_many({"document_id": doc_id})
    db.sheet_rows.delete_many({"document_id": doc_id})
    pages = []

    if kind == "pdf":
        total = pdf.count_pages(path)
        db.documents.update_one({"_id": doc_id}, {"$set": {"page_count": total}})
        for p in pdf.iter_pdf_pages(path):
            save_page(doc_id, p)
            pages.append(p)
            db.documents.update_one({"_id": doc_id}, {"$set": {
                "progress": round(p.page_no / total, 3), "heartbeat_at": now()}})
    elif kind in ("jpg", "png", "tiff"):
        for p in image.iter_image_pages(path):
            save_page(doc_id, p)
            pages.append(p)
            db.documents.update_one({"_id": doc_id}, {"$set": {"heartbeat_at": now()}})
        db.documents.update_one({"_id": doc_id}, {"$set": {"page_count": len(pages)}})
    else:  # csv, xlsx, xls
        pages, rows_by_sheet = spreadsheet.parse_spreadsheet(path, kind)
        for p in pages:
            save_page(doc_id, p)
        for sheet, rows in rows_by_sheet.items():
            if rows:
                db.sheet_rows.insert_many(
                    [{"document_id": doc_id, "sheet": sheet, "row_no": i, "data": r}
                     for i, r in enumerate(rows, start=1)])
        db.documents.update_one({"_id": doc_id}, {"$set": {"page_count": len(pages)}})

    event(doc_id, "text_extraction", "ok", t0)
    if not pages or all(p.source == "error" for p in pages):
        raise ValueError("No pages could be processed")

    bad = [p for p in pages if p.source == "error"
           or (p.ocr_confidence is not None and p.ocr_confidence < LOW_CONF)]
    db.documents.update_one({"_id": doc_id}, {"$set": {"progress": 1.0, "low_quality_pages": [p.page_no for p in bad]}})
    return "needs_review" if bad else "completed"

def main():
    init_indexes()
    print("Worker started. Waiting for jobs...")
    while True:
        recover_stale()
        doc = claim_next()
        if not doc:
            time.sleep(1.5)
            continue
        print(f"Processing {doc['filename']} ({doc['_id']})")
        t0 = time.time()
        try:
            status = process(doc)
            db.documents.update_one({"_id": doc["_id"]}, {"$set": {"status": status, "finished_at": now()}})
            print(f"  -> {status} in {time.time() - t0:.1f}s")
        except Exception as e:
            event(doc["_id"], "processing", "failed", t0, str(e))
            db.documents.update_one({"_id": doc["_id"]},
                {"$set": {"status": "failed", "error_message": str(e), "finished_at": now()}})
            print(f"  -> failed: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    main()