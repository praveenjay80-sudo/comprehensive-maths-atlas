"""Runtime "sync now" against mathprobvault.com.

A full re-crawl takes several minutes (13k+ pages), so `sync_now` kicks it
off as a background asyncio task and returns immediately; `get_status` polls
progress. On completion the in-memory Store is hot-swapped -- this does not
touch the committed data/ files (see store.py's refresh docstring); for a
permanent update, re-run scripts/build_data.py against a fresh
scripts/fetch_mathprobvault.py pull and redeploy.
"""
import asyncio
from datetime import datetime, timezone

from . import mpv_fetch
from .store import store

_state: dict = {"status": "idle"}  # idle | running | done | error
_task: asyncio.Task | None = None


def get_status() -> dict:
    return dict(_state)


async def _run():
    global _state
    _state = {"status": "running", "fetched": 0, "queueLen": 0}

    def progress_cb(fetched: int, queue_len: int):
        _state["fetched"] = fetched
        _state["queueLen"] = queue_len

    try:
        before_ids = set(store.by_id.keys())
        bundle = await mpv_fetch.crawl(progress_cb=progress_cb)

        after_ids = {t["id"] for t in bundle["topics"]}
        added_ids = after_ids - before_ids
        removed_ids = before_ids - after_ids

        by_id_before = store.by_id
        by_id_after = {t["id"]: t for t in bundle["topics"]}
        changed_ids = {
            tid for tid in (after_ids & before_ids)
            if by_id_before[tid]["title"] != by_id_after[tid]["title"]
            or by_id_before[tid]["count"] != by_id_after[tid]["count"]
        }

        added = sorted(({"id": tid, "title": by_id_after[tid]["title"]} for tid in added_ids),
                        key=lambda x: x["title"] or "")
        removed = sorted(({"id": tid, "title": by_id_before[tid]["title"]} for tid in removed_ids),
                          key=lambda x: x["title"] or "")
        changed = sorted(({"id": tid, "title": by_id_after[tid]["title"]} for tid in changed_ids),
                          key=lambda x: x["title"] or "")

        synced_at = datetime.now(timezone.utc).isoformat()
        was_up_to_date = not added and not removed and not changed
        store.refresh(bundle, synced_at)

        _state = {
            "status": "done",
            "syncedAt": synced_at,
            "topicCount": len(bundle["topics"]),
            "wasAlreadyUpToDate": was_up_to_date,
            "added": added,
            "removed": removed,
            "changed": changed,
        }
    except Exception as exc:
        _state = {"status": "error", "error": str(exc)}


async def sync_now() -> dict:
    global _task
    if _state.get("status") == "running":
        return get_status()
    _task = asyncio.create_task(_run())
    await asyncio.sleep(0)  # let it start
    return get_status()
