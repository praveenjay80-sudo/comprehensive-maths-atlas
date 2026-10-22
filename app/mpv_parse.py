"""Shared mathprobvault.com HTML parsing + DAG-build logic.

Used by scripts/build_data.py (one-off build from cached HTML) and
app/mpv_fetch.py (live re-crawl for the in-app sync feature) so the parsing
and cycle-cutting logic stays in exactly one place.
"""
import html as html_lib
import re
import sys

BASE = "https://www.mathprobvault.com"

ROOT_SLUGS = [
    "discrete-mathematics-computer-science",
    "analysis",
    "probability-statistics",
    "algebra",
    "topology-geometry",
    "differential-equations",
    "number-theory",
    "mathematical-physics",
    "numerical-analysis",
    "logic-foundations",
    "optimization",
    "techniques",
]

H1_RE = re.compile(r"<h1[^>]*>([^<]+)</h1>")
COUNT_RE = re.compile(
    r'\[<span[^>]*>(\d+)</span>/<span[^>]*>(\d+)<!-- -->%</span>\]'
)
LINK_RE = re.compile(
    r'<a[^>]*href="(/navigation/[a-z0-9\-/]+)"[^>]*>([^<]+)</a>.*?'
    r'\[<span[^>]*>(\d+)</span>/<span[^>]*>(\d+)<!-- -->%</span>\]'
)


def url_to_id(url: str) -> str:
    prefix = BASE + "/navigation/"
    assert url.startswith(prefix), url
    return url[len(prefix):]


def parse_page(page_html: str):
    """Returns (title, count, pct, subtopics) where subtopics is a list of
    {href, name, count, pct} dicts."""
    sec_idx = page_html.find(">Subtopics<")
    if sec_idx == -1:
        header_html = page_html
        section_html = ""
    else:
        header_html = page_html[:sec_idx]
        section_html = page_html[sec_idx:]

    h1_match = H1_RE.search(header_html)
    title = html_lib.unescape(h1_match.group(1)).strip() if h1_match else None

    count_matches = list(COUNT_RE.finditer(header_html))
    count, pct = (None, None)
    if count_matches:
        last = count_matches[-1]
        count, pct = int(last.group(1)), int(last.group(2))

    subtopics = []
    for m in LINK_RE.finditer(section_html):
        href, name, sub_count, sub_pct = m.groups()
        subtopics.append({
            "href": href,
            "name": html_lib.unescape(name).strip(),
            "count": int(sub_count),
            "pct": int(sub_pct),
        })
    return title, count, pct, subtopics


def build_topics(nodes: dict) -> tuple[list[dict], int]:
    """nodes: url -> {title, count, pct, child_urls}.

    Returns (topics, cut_edges) where topics mirrors data/topics.json's shape.
    DFS with white/gray/black coloring: shared descendants (DAG) are fine and
    reused by id; a back-edge to an in-progress ancestor (true cycle) is cut.
    """
    color: dict[str, str] = {}
    out: dict[str, dict] = {}
    cut_edges = 0

    def dfs(url: str, depth: int) -> dict:
        nonlocal cut_edges
        nid = url_to_id(url)
        n = nodes.get(url)
        rec = {
            "id": nid,
            "title": n["title"] if n else None,
            "count": n["count"] if n else None,
            "pct": n["pct"] if n else None,
            "parentIds": [],
            "childIds": [],
            "depth": depth,
        }
        out[url] = rec
        color[url] = "gray"
        if n:
            for cu in n["child_urls"]:
                c = color.get(cu)
                if c == "gray":
                    cut_edges += 1
                    continue
                if c == "black":
                    child_rec = out[cu]
                    rec["childIds"].append(child_rec["id"])
                    if rec["id"] not in child_rec["parentIds"]:
                        child_rec["parentIds"].append(rec["id"])
                    child_rec["depth"] = min(child_rec["depth"], depth + 1)
                    continue
                child_rec = dfs(cu, depth + 1)
                rec["childIds"].append(child_rec["id"])
                if rec["id"] not in child_rec["parentIds"]:
                    child_rec["parentIds"].append(rec["id"])
        color[url] = "black"
        return rec

    sys.setrecursionlimit(10000)
    for slug in ROOT_SLUGS:
        dfs(BASE + "/navigation/" + slug, 0)

    return list(out.values()), cut_edges
