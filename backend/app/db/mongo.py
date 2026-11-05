from pymongo import MongoClient, ASCENDING, TEXT
from app.config import settings

client = MongoClient(settings.mongodb_url, serverSelectionTimeoutMS=5000)
db = client[settings.mongodb_db]

def init_indexes() -> None:
    db.documents.create_index([("sha256", ASCENDING)])
    db.documents.create_index([("status", ASCENDING), ("created_at", ASCENDING)])
    db.pages.create_index([("document_id", ASCENDING), ("page_no", ASCENDING)], unique=True)
    db.pages.create_index([("text", TEXT)], name="page_text_search")
    db.extractions.create_index([("document_id", ASCENDING)])
    db.validation_issues.create_index([("document_id", ASCENDING)])
    db.processing_events.create_index([("document_id", ASCENDING)])
    db.corrections.create_index([("document_id", ASCENDING)])
    db.chunks.create_index([("document_id", ASCENDING)])
