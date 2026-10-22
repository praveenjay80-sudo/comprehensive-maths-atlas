"""In-memory dataset loaded once at startup from the lean data/ files."""
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load(name: str):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


class Store:
    def __init__(self) -> None:
        self.topics: list[dict] = _load("topics.json")
        self.roots: list[str] = _load("roots.json")
        self.meta: dict = _load("meta.json")
        self.by_id: dict[str, dict] = {t["id"]: t for t in self.topics}
        self.last_synced_at: str | None = None

    def refresh(self, bundle: dict, synced_at: str) -> None:
        """Hot-swap the in-memory dataset after a runtime sync.

        Does not write to disk -- the committed data/ files are only updated
        by re-running scripts/fetch_mathprobvault.py + scripts/build_data.py
        and redeploying. This keeps a live "check for updates" fast and free
        of write contention, at the cost of the refresh being lost on restart.
        """
        self.topics = bundle["topics"]
        self.roots = bundle["roots"]
        self.meta = bundle["meta"]
        self.by_id = {t["id"]: t for t in self.topics}
        self.last_synced_at = synced_at

    def get(self, topic_id: str) -> dict | None:
        return self.by_id.get(topic_id)

    def get_roots(self) -> list[dict]:
        return [self.by_id[r] for r in self.roots if r in self.by_id]

    def get_children(self, topic_id: str) -> list[dict]:
        topic = self.by_id.get(topic_id)
        if not topic:
            return []
        return [self.by_id[c] for c in topic["childIds"] if c in self.by_id]

    def get_parents(self, topic_id: str) -> list[dict]:
        topic = self.by_id.get(topic_id)
        if not topic:
            return []
        return [self.by_id[p] for p in topic["parentIds"] if p in self.by_id]

    def get_breadcrumb(self, topic_id: str) -> list[dict]:
        """Walk parentIds up to a root, picking the first parent at each
        step (a topic can have multiple parents when shared across
        branches -- the breadcrumb just shows one real path to it)."""
        trail = []
        seen = set()
        current = self.by_id.get(topic_id)
        while current and current["id"] not in seen:
            trail.append(current)
            seen.add(current["id"])
            if not current["parentIds"]:
                break
            current = self.by_id.get(current["parentIds"][0])
        trail.reverse()
        return trail

    def get_siblings(self, topic_id: str) -> list[dict]:
        topic = self.by_id.get(topic_id)
        if not topic or not topic["parentIds"]:
            return []
        parent = self.by_id.get(topic["parentIds"][0])
        if not parent:
            return []
        return [
            self.by_id[c] for c in parent["childIds"]
            if c in self.by_id and c != topic_id
        ]

    def search(self, query: str, limit: int = 30) -> list[dict]:
        q = query.strip().lower()
        if not q:
            return []
        starts, contains = [], []
        for t in self.topics:
            title = (t["title"] or "").lower()
            if title.startswith(q):
                starts.append(t)
            elif q in title:
                contains.append(t)
            if len(starts) >= limit:
                break
        results = (starts + contains)[:limit]
        return results


store = Store()
