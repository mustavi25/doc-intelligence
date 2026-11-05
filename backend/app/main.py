from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.db.mongo import client, db, init_indexes
from app.api.documents import router as documents_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_indexes()
    yield


app = FastAPI(title="Document Intelligence API", lifespan=lifespan)
app.include_router(documents_router)


@app.get("/api/health")
def health():
    client.admin.command("ping")
    return {"status": "ok", "db": "connected", "collections": db.list_collection_names()}