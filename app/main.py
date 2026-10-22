import os

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import cache, generate, sync
from .store import store

app = FastAPI(title="Comprehensive Maths Atlas")


@app.get("/api/meta")
def get_meta():
    return {**store.meta, "lastSyncedAt": store.last_synced_at}


@app.get("/api/roots")
def get_roots():
    return store.get_roots()


@app.get("/api/models")
def get_models():
    return {"models": generate.MODELS, "default": generate.DEFAULT_MODEL}


@app.get("/api/search")
def search(q: str = ""):
    return store.search(q)


@app.get("/api/topics/{topic_id:path}")
def get_topic(topic_id: str):
    topic = store.get(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    return {
        "topic": topic,
        "breadcrumb": store.get_breadcrumb(topic_id),
        "children": store.get_children(topic_id),
        "siblings": store.get_siblings(topic_id),
        "parents": store.get_parents(topic_id),
    }


class GenerateRequest(BaseModel):
    apiKey: str
    model: str | None = None
    forceRegenerate: bool = False


async def _generate_or_cached(topic_id: str, body: GenerateRequest, kind: str, generator_fn):
    topic = store.get(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    if not body.apiKey:
        raise HTTPException(status_code=400, detail="Missing OpenRouter API key")

    model = body.model or generate.DEFAULT_MODEL

    if not body.forceRegenerate:
        cached = cache.get(topic_id, model, kind)
        if cached:
            return {"cached": True, **cached}

    breadcrumb = store.get_breadcrumb(topic_id)
    siblings = store.get_siblings(topic_id)
    children = store.get_children(topic_id)

    try:
        result = await generator_fn(topic, breadcrumb, siblings, children, body.apiKey, model)
    except Exception as exc:  # surfaced to the UI, not swallowed
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    cache.put(topic_id, model, kind, result)
    return {"cached": False, **result}


@app.post("/api/topics/{topic_id:path}/explain")
async def get_explanation(topic_id: str, body: GenerateRequest):
    return await _generate_or_cached(topic_id, body, "explain", generate.generate_explanation)


@app.post("/api/topics/{topic_id:path}/reading-list")
async def get_reading_list(topic_id: str, body: GenerateRequest):
    return await _generate_or_cached(topic_id, body, "reading_list", generate.generate_reading_list)


@app.get("/api/sync/status")
def sync_status():
    return sync.get_status()


@app.post("/api/sync")
async def sync_trigger():
    return await sync.sync_now()


STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
# On Vercel, vercel.json routes static assets directly (separate build
# output) so this function's bundle may not include static/ at all --
# only mount it when present (local dev, Railway, etc.).
if os.path.isdir(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
