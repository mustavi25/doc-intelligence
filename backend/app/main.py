from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from app.db.mongo import client, db, init_indexes
from app.api.documents import router as documents_router
from app.api.search import router as search_router
from app.api.metrics import router as metrics_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_indexes()
    yield


app = FastAPI(title="Document Intelligence API", lifespan=lifespan)

app.include_router(documents_router)
app.include_router(search_router)
app.include_router(metrics_router)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)

    def fix(node):
        if isinstance(node, dict):
            if node.get("contentMediaType") == "application/octet-stream":
                node.pop("contentMediaType")
                node["format"] = "binary"
            for v in node.values():
                fix(v)
        elif isinstance(node, list):
            for v in node:
                fix(v)

    fix(schema)
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi


@app.get("/")
def root():
    return {"service": "Document Intelligence API", "docs": "/docs", "health": "/api/health"}


@app.get("/api/health")
def health():
    client.admin.command("ping")
    return {"status": "ok", "db": "connected", "collections": db.list_collection_names()}