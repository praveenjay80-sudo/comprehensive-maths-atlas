"""Standalone CLI: live-crawl mathprobvault.com and write data/topics.json,
data/roots.json, data/meta.json directly (no data/raw/ HTML cache needed --
app/mpv_fetch.py parses each page in memory as it's fetched).

This is the same crawler app/sync.py runs in-process for the live "Sync now"
button; running it here just writes straight to the committed data/ files for
a permanent dataset refresh (commit + redeploy after running).
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import mpv_fetch  # noqa: E402

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def progress_cb(fetched: int, queue_len: int):
    if fetched % 200 == 0:
        print(f"[fetch] {fetched} fetched, {queue_len} queued", file=sys.stderr, flush=True)


async def main():
    bundle = await mpv_fetch.crawl(progress_cb=progress_cb)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "topics.json").write_text(
        json.dumps(bundle["topics"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (DATA_DIR / "roots.json").write_text(
        json.dumps(bundle["roots"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (DATA_DIR / "meta.json").write_text(
        json.dumps(bundle["meta"], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"DONE. topics={len(bundle['topics'])} cycleEdgesCut={bundle['meta']['cycleEdgesCut']}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
