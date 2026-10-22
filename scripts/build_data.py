"""Rebuild data/topics.json, data/roots.json, data/meta.json from cached HTML
in data/raw/ (or a path given as argv[1]).

Parsing and cycle-cutting logic lives in app/mpv_parse.py, shared with the
live re-crawl used by the in-app sync feature (app/mpv_fetch.py).
"""
import json
import sys
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import mpv_parse  # noqa: E402

ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT_DIR / "data" / "raw")
DATA_DIR = ROOT_DIR / "data"


def url_to_cache_path(url: str) -> Path:
    import re
    key = re.sub(r"[^a-zA-Z0-9]", "_", url)[:200] + ".html"
    return RAW_DIR / key


def main():
    nodes = {}  # url -> {title, count, pct, child_urls}
    queue = deque(mpv_parse.BASE + "/navigation/" + slug for slug in mpv_parse.ROOT_SLUGS)
    enqueued = set(queue)
    missing = 0

    while queue:
        url = queue.popleft()
        cache_path = url_to_cache_path(url)
        if not cache_path.exists():
            missing += 1
            continue
        page_html = cache_path.read_text(encoding="utf-8")
        title, count, pct, subtopics = mpv_parse.parse_page(page_html)
        child_urls = [mpv_parse.BASE + st["href"] for st in subtopics]
        nodes[url] = {"title": title, "count": count, "pct": pct, "child_urls": child_urls}
        for cu in child_urls:
            if cu not in enqueued:
                enqueued.add(cu)
                queue.append(cu)
        if len(nodes) % 1000 == 0:
            print(f"[parse] {len(nodes)} nodes, queue={len(queue)}, missing={missing}", file=sys.stderr, flush=True)

    print(f"Parsed {len(nodes)} nodes from cache, missing={missing}", file=sys.stderr, flush=True)

    topics, cut_edges = mpv_parse.build_topics(nodes)
    print(f"Cycle edges cut: {cut_edges}", file=sys.stderr)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "topics.json").write_text(
        json.dumps(topics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (DATA_DIR / "roots.json").write_text(
        json.dumps(mpv_parse.ROOT_SLUGS, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    meta = {
        "sourceUrl": mpv_parse.BASE + "/#topics",
        "topicCount": len(topics),
        "cycleEdgesCut": cut_edges,
        "builtAt": datetime.now(timezone.utc).isoformat(),
    }
    (DATA_DIR / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"DONE. topics={len(topics)}", file=sys.stderr)


if __name__ == "__main__":
    main()
