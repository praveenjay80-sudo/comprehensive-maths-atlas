"""Live async re-crawl of mathprobvault.com's /navigation/* tree.

Used by app/sync.py for the in-app "check for updates" / "sync now" feature.
Mirrors the original scratchpad crawler (breadth-first worker pool) but async
via httpx instead of a Node worker pool, and feeds app/mpv_parse.py for the
actual HTML parsing + cycle-safe DAG build.
"""
import asyncio
from collections import deque
from datetime import datetime, timezone
from typing import Callable

import httpx

from . import mpv_parse

CONCURRENCY = 16


async def crawl(progress_cb: Callable[[int, int], None] | None = None) -> dict:
    """Crawls the live site, returns a bundle shaped like
    {"topics": [...], "roots": [...], "meta": {...}}."""
    nodes: dict[str, dict] = {}
    queue: deque[str] = deque(
        mpv_parse.BASE + "/navigation/" + slug for slug in mpv_parse.ROOT_SLUGS
    )
    enqueued = set(queue)
    lock = asyncio.Lock()
    fetched = 0
    failed = 0

    async def worker(client: httpx.AsyncClient):
        nonlocal fetched, failed
        while True:
            async with lock:
                if not queue:
                    return
                url = queue.popleft()
            try:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                resp.raise_for_status()
                title, count, pct, subtopics = mpv_parse.parse_page(resp.text)
                child_urls = [mpv_parse.BASE + st["href"] for st in subtopics]
                nodes[url] = {"title": title, "count": count, "pct": pct, "child_urls": child_urls}
                async with lock:
                    fetched += 1
                    for cu in child_urls:
                        if cu not in enqueued:
                            enqueued.add(cu)
                            queue.append(cu)
                    if progress_cb:
                        progress_cb(fetched, len(queue))
            except Exception:
                async with lock:
                    failed += 1

    async with httpx.AsyncClient(timeout=30) as client:
        workers = [asyncio.create_task(worker(client)) for _ in range(CONCURRENCY)]
        await asyncio.gather(*workers)

    topics, cut_edges = mpv_parse.build_topics(nodes)
    meta = {
        "sourceUrl": mpv_parse.BASE + "/#topics",
        "topicCount": len(topics),
        "cycleEdgesCut": cut_edges,
        "builtAt": datetime.now(timezone.utc).isoformat(),
        "fetchFailures": failed,
    }
    return {"topics": topics, "roots": list(mpv_parse.ROOT_SLUGS), "meta": meta}
