"""On-demand explain-page and reading-list generation via OpenRouter."""
import httpx

from . import json_salvage

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

MODELS = [
    {"id": "anthropic/claude-sonnet-4.5", "label": "Claude Sonnet 4.5", "tier": "balanced"},
    {"id": "anthropic/claude-opus-4.5", "label": "Claude Opus 4.5", "tier": "highest quality"},
    {"id": "anthropic/claude-haiku-4.5", "label": "Claude Haiku 4.5", "tier": "fast/cheap"},
    {"id": "openai/gpt-4.1", "label": "GPT-4.1", "tier": "balanced"},
    {"id": "openai/o4-mini", "label": "OpenAI o4-mini", "tier": "reasoning"},
    {"id": "openai/gpt-4o-mini", "label": "GPT-4o mini", "tier": "fast/cheap"},
    {"id": "google/gemini-2.5-pro", "label": "Gemini 2.5 Pro", "tier": "highest quality"},
    {"id": "google/gemini-2.5-flash", "label": "Gemini 2.5 Flash", "tier": "fast/cheap"},
    {"id": "deepseek/deepseek-chat-v3.1", "label": "DeepSeek V3.1", "tier": "balanced"},
    {"id": "deepseek/deepseek-r1-0528", "label": "DeepSeek R1", "tier": "reasoning"},
    {"id": "meta-llama/llama-3.3-70b-instruct", "label": "Llama 3.3 70B", "tier": "fast/cheap"},
    {"id": "mistralai/mistral-large", "label": "Mistral Large", "tier": "balanced"},
    {"id": "qwen/qwen3-235b-a22b", "label": "Qwen3 235B", "tier": "balanced"},
    {"id": "x-ai/grok-4.3", "label": "Grok 4.3", "tier": "highest quality"},
]
DEFAULT_MODEL = "anthropic/claude-sonnet-4.5"

EXPLAIN_SYSTEM_PROMPT = """You are a gifted math educator building an "Explain" \
page for one specific topic inside a large hierarchical index of math fields, \
drawn from a catalogue of textbook problems. You are given the topic's title, \
its place in the field hierarchy (breadcrumb), and sibling/child topic names \
purely as your own private grounding.

Respond with ONLY a single JSON object, no markdown fences, no commentary, \
matching exactly this shape:

{
  "beginner": {
    "tldr": "one plain-English sentence a total beginner can understand, zero jargon, zero notation",
    "explanation": "4-7 short paragraphs building real intuition from scratch: what problem this topic responds to, what it actually says/does in everyday language, and how it connects to things a beginner already knows. No mathematical notation, no unexplained jargon -- if a technical term is unavoidable, define it in the same sentence in plain words.",
    "analogy": "one vivid, concrete real-world analogy or mental picture that captures the core idea",
    "crossDomainExamples": [
      {"domain": "a field unrelated to math, e.g. weather, sports, cooking, music", "example": "2-4 sentences showing the same underlying idea playing out in that domain"},
      {"domain": "a different unrelated field", "example": "2-4 sentences"}
    ],
    "commonMisconceptions": ["short beginner misconception #1 and the correction", "short beginner misconception #2 and the correction"],
    "trapsToAvoid": ["a specific mistake learners make with this exact topic, and how to avoid it"],
    "glossary": [{"term": "a technical word used above", "definition": "one plain-language sentence"}],
    "checkYourself": {
      "question": "one multiple-choice question testing the core intuition, answerable without formal notation",
      "options": ["option A", "option B", "option C"],
      "correctIndex": 0,
      "explanation": "1-2 sentences on why that option is correct"
    }
  },
  "advanced": {
    "formalStatement": "the precise formal statement/definition, LaTeX notation welcome (wrap inline math in \\\\( \\\\) and display math in \\\\[ \\\\])",
    "keyIdeaOrProofSketch": "3-6 paragraphs: the key derivation, proof sketch, or technical mechanism, at the level of a course in this subject",
    "workedExample": "one fully worked example or computation illustrating the topic, with notation",
    "furtherContext": "1-2 paragraphs on how this connects to neighboring topics, generalizations, or where it's used in more advanced work"
  }
}

Rules:
- Never invent false mathematical claims. If genuinely unsure of a precise formal detail, phrase it with appropriate hedging rather than asserting it confidently.
- 2 to 4 items each in commonMisconceptions, trapsToAvoid, glossary.
- Exactly 2 items in crossDomainExamples, from two different unrelated domains.
- checkYourself must have exactly 3 options with exactly one correct.
"""

READING_LIST_SYSTEM_PROMPT = """You are a research librarian building a rigorous, \
self-study "zero to mastery" reading path for one specific topic inside a large \
hierarchical index of math fields. You are given the topic's title and its place \
in the field hierarchy, purely as your own private grounding.

Respond with ONLY a single JSON object, no markdown fences, no commentary, \
matching exactly this shape:

{
  "overview": "2-3 sentences on how to approach studying this topic and in what order",
  "readings": [
    {
      "stage": "Zero / Absolute beginner" | "Foundations" | "Core" | "Advanced" | "Research / primary sources",
      "title": "exact, real, verifiable title of a book, paper, lecture notes, or course",
      "author": "author or institution",
      "format": "textbook chapter | monograph | paper | lecture notes | online course",
      "locator": "chapter/section/arXiv id if known, else empty string",
      "url": "a direct link ONLY if you are genuinely confident it is correct -- a doi.org/<DOI> link for a paper with a known DOI, an arxiv.org/abs/<id> link for an arXiv paper, otherwise empty string",
      "about": "2-3 sentences on what this specific work covers",
      "why": "1 sentence on this work's role at this stage of learning the topic"
    }
  ]
}

Rules:
- Only cite real, verifiable, well-known works. Never invent a title, author, or edition.
- Prefer works you have high confidence actually exist and match the stated author.
- Never fabricate a DOI, arXiv id, or URL. A wrong link is worse than no link: only fill in "url" \
when you are genuinely confident of the exact DOI/arXiv id, not merely that the paper likely has one. \
Books and lecture notes usually don't have a DOI -- leave "url" empty for those unless you know a \
specific stable link (e.g. the book's own arXiv preprint). When unsure in any way, leave "url" as "".
- "Zero / Absolute beginner" should assume no background at all in this specific topic -- popular-level or first-contact material.
- "Research / primary sources" should include the historically or technically primary sources where appropriate.
- Produce 10 to 18 total reading entries across all five stages, at least one per stage.
"""


def _fmt_names(topics: list[dict], limit: int = 8) -> str:
    names = [t["title"] for t in topics[:limit] if t.get("title")]
    return ", ".join(names) if names else "(none)"


def _build_user_prompt(topic: dict, breadcrumb: list[dict], siblings: list[dict],
                        children: list[dict], task_line: str) -> str:
    path = " > ".join(t["title"] for t in breadcrumb if t.get("title"))
    return f"""Topic: {topic['title']}
Field hierarchy: {path}
Sibling topics (same parent): {_fmt_names(siblings)}
Child topics (subtopics of this one, if any): {_fmt_names(children)}
Source catalogue problem count for this topic: {topic.get('count')}

{task_line}
"""


async def _call_openrouter(system_prompt: str, user_prompt: str, api_key: str, model: str,
                            max_tokens: int) -> dict:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.4,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://comprehensive-maths-atlas.example",
        "X-Title": "Comprehensive Maths Atlas",
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(OPENROUTER_URL, headers=headers, json=payload)

    if resp.status_code != 200:
        raise RuntimeError(f"OpenRouter error {resp.status_code}: {resp.text[:500]}")

    data = resp.json()
    choice = data["choices"][0]
    content = choice["message"]["content"]
    if not content:
        raise RuntimeError(
            f"Empty completion from model (finish_reason={choice.get('finish_reason')})"
        )

    parsed, truncated = json_salvage.parse_lenient(content)
    if truncated:
        parsed["_truncated"] = True
    return parsed


async def generate_explanation(topic: dict, breadcrumb: list[dict], siblings: list[dict],
                                children: list[dict], api_key: str, model: str) -> dict:
    user_prompt = _build_user_prompt(
        topic, breadcrumb, siblings, children,
        f'Explain "{topic["title"]}" now, producing both the beginner and advanced blocks.',
    )
    return await _call_openrouter(EXPLAIN_SYSTEM_PROMPT, user_prompt, api_key, model, max_tokens=4500)


async def generate_reading_list(topic: dict, breadcrumb: list[dict], siblings: list[dict],
                                 children: list[dict], api_key: str, model: str) -> dict:
    user_prompt = _build_user_prompt(
        topic, breadcrumb, siblings, children,
        f'Build the zero-to-mastery reading path for "{topic["title"]}" now.',
    )
    return await _call_openrouter(READING_LIST_SYSTEM_PROMPT, user_prompt, api_key, model, max_tokens=4000)
