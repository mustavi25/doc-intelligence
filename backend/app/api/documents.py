import hashlib, os, uuid
from datetime import datetime, timezone
from pathlib import Path
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from app.config import settings
from app.db.mongo import db

router = APIRouter(prefix="/api/documents", tags=["documents"])
UPLOAD_DIR = Path(settings.upload_dir).resolve()
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_EXT = {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".xlsx", ".xls", ".csv"}
MAX_BYTES = 200 * 1024 * 1024

def now():
    return datetime.now(timezone.utc)

def oid(doc_id: str) -> ObjectId:
    try:
        return ObjectId(doc_id)
    except InvalidId:
        raise HTTPException(404, "Document not found")

def _jsonable(v):
    if isinstance(v, ObjectId):
        return str(v)
    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_jsonable(x) for x in v]
    return v


def ser(d: dict) -> dict:
    d = dict(d)
    d["id"] = str(d.pop("_id"))
    return _jsonable(d)

@router.post("", status_code=202)
async def upload(files: list[UploadFile] = File(...)):
    out = []
    for f in files:
        ext = os.path.splitext(f.filename or "")[1].lower()
        if ext not in ALLOWED_EXT:
            out.append({"filename": f.filename, "error": f"Unsupported file type '{ext}'"})
            continue
        stored = UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
        h, size = hashlib.sha256(), 0
        with open(stored, "wb") as dst:
            while chunk := await f.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_BYTES:
                    break
                h.update(chunk)
                dst.write(chunk)
        if size > MAX_BYTES:
            stored.unlink(missing_ok=True)
            out.append({"filename": f.filename, "error": "File too large"})
            continue
        sha = h.hexdigest()
        dup = db.documents.find_one({"sha256": sha}, {"_id": 1})
        res = db.documents.insert_one({
            "filename": f.filename, "storage_path": str(stored), "size_bytes": size,
            "sha256": sha, "duplicate_of": dup["_id"] if dup else None,
            "file_type": None, "status": "queued", "progress": 0.0,
            "page_count": None, "error_message": None, "attempts": 0,
            "created_at": now(),
        })
        out.append({"id": str(res.inserted_id), "filename": f.filename, "status": "queued",
                    "duplicate_of": str(dup["_id"]) if dup else None})
    return {"documents": out}

@router.get("")
def list_documents(status: str | None = None, limit: int = Query(50, le=200), skip: int = 0):
    q = {"status": status} if status else {}
    docs = db.documents.find(q).sort("created_at", -1).skip(skip).limit(limit)
    return {"total": db.documents.count_documents(q), "items": [ser(d) for d in docs]}

@router.get("/{doc_id}")
def get_document(doc_id: str):
    d = db.documents.find_one({"_id": oid(doc_id)})
    if not d:
        raise HTTPException(404, "Document not found")
    events = list(db.processing_events.find({"document_id": d["_id"]}, {"_id": 0, "document_id": 0}))
    return {**ser(d), "events": events}

@router.get("/{doc_id}/pages")
def get_pages(doc_id: str):
    pages = db.pages.find({"document_id": oid(doc_id)}, {"_id": 0, "document_id": 0}).sort("page_no", 1)
    return {"pages": list(pages)}

@router.post("/{doc_id}/reprocess", status_code=202)
def reprocess(doc_id: str):
    r = db.documents.update_one(
        {"_id": oid(doc_id), "status": {"$in": ["failed", "needs_review", "completed"]}},
        {"$set": {"status": "queued", "error_message": None, "progress": 0.0}})
    if not r.matched_count:
        raise HTTPException(409, "Document not found or currently processing")
    return {"id": doc_id, "status": "queued"}

@router.get("/{doc_id}/result")
def get_result(doc_id: str):
    ex = db.extractions.find_one({"document_id": oid(doc_id)}, sort=[("version", -1)])
    if not ex:
        raise HTTPException(404, "No extraction yet")
    return ser(ex)