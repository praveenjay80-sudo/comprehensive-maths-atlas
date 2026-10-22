# Comprehensive Maths Atlas

A browsable index of [mathprobvault.com](https://www.mathprobvault.com)'s full
field hierarchy — 13,448 topics across 12 top-level math fields, 5+ levels deep
(field → subfield → topic → subtopic → ...). For any topic, generate on demand:

- An **Explain page** (Beginner/Advanced toggle, analogies, cross-domain examples,
  worked examples, common misconceptions, a plain-language glossary, and a
  self-check question) via an LLM through OpenRouter (your own API key, stored
  only in your browser).
- A **zero-to-mastery reading list**, staged from absolute-beginner to
  research-level, citing real books/papers/courses.

Generated content is cached server-side forever after the first generation, so
nothing is ever regenerated twice for the same topic+model.

## Stack

FastAPI backend (`app/`) serving a plain HTML/CSS/JS frontend (`static/`, no
build step). SQLite cache (`data/cache.db`, gitignored) for generated content,
keyed by `(topic_id, model, kind)`.

## Rebuilding the dataset

The committed `data/topics.json` / `roots.json` / `meta.json` were built from a
full crawl of mathprobvault.com's `/navigation/*` tree. To refresh them from a
live pull:

```bash
python scripts/fetch_mathprobvault.py   # live crawl -> topics.json, roots.json, meta.json directly
```

`scripts/build_data.py` is the alternate path used for the very first build,
which went through a local cache of raw HTML files instead of a live crawl;
both share the same parsing/cycle-cutting logic in `app/mpv_parse.py`.

The running app also has a live "Sync now" action (`POST /api/sync`) that
re-crawls the site and hot-swaps the in-memory dataset with any added/removed/
changed topics, without touching the committed data/ files or needing a
redeploy — see `app/sync.py`.

## Run locally

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Deploy

Railway, via `Procfile` / `railway.json` (`railway up`).
