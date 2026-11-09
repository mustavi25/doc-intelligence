import numpy as np
from fastapi import APIRouter
from app.db.mongo import db

router = APIRouter(prefix="/api", tags=["metrics"])


@router.get("/metrics")
def metrics():
    by_status = {r["_id"]: r["n"] for r in db.documents.aggregate(
        [{"$group": {"_id": "$status", "n": {"$sum": 1}}}])}
    done = by_status.get("completed", 0) + by_status.get("needs_review", 0)
    failed = by_status.get("failed", 0)
    finished = done + failed

    secs = [(d["finished_at"] - d["started_at"]).total_seconds()
            for d in db.documents.find({"finished_at": {"$ne": None}, "started_at": {"$ne": None}},
                                       {"started_at": 1, "finished_at": 1})]
    stages = {r["_id"]: round(r["avg_ms"], 1) for r in db.processing_events.aggregate(
        [{"$match": {"status": "ok"}}, {"$group": {"_id": "$stage", "avg_ms": {"$avg": "$duration_ms"}}}])}
    return {
        "total_documents": sum(by_status.values()),
        "by_status": by_status,
        "success_rate": round(done / finished, 4) if finished else None,
        "failure_rate": round(failed / finished, 4) if finished else None,
        "avg_processing_seconds": round(float(np.mean(secs)), 2) if secs else None,
        "p95_processing_seconds": round(float(np.percentile(secs, 95)), 2) if secs else None,
        "avg_stage_ms": stages,
        "open_issues": db.validation_issues.count_documents({"resolved": False}),
        "corrections_made": db.corrections.count_documents({}),
    }