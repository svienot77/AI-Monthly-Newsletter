"""
generate_newsletter.py — Autonomously generate the AI Pulse newsletter via Anthropic API.

Two-phase approach:
  Phase 1 (research_news): Claude + web_search tool → structured JSON with all content
  Phase 2 (build_html):    Claude (no tools) + template → filled-in HTML string

Public entry point: generate(extra_topics, publish_date) → HTML string (in-memory, no disk writes)
"""

import json
import os
from datetime import date
from pathlib import Path

import anthropic
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

TEMPLATE_PATH = ROOT / "tools" / "newsletter_template.html"

RESEARCH_SYSTEM = """You are a research assistant for the AI Pulse newsletter, targeting \
Microsoft Support leadership (technical and strategic focus).

You have access to the web_search tool. Run every search listed in the user message, \
then synthesize all findings into a single JSON object matching the schema below. \
Return RAW JSON ONLY — no markdown fences, no explanation, no surrounding text.

JSON schema:
{
  "intro": "<2-3 sentence editorial paragraph, ~60 words, sets the strategic tone>",
  "takeaways": [
    {"label": "<bold label>", "text": "<one sentence>"}
  ],
  "deep_dive_title": "<headline for the most significant story this month>",
  "deep_dive_body_paragraphs": ["<p style=\\"margin:0 0 14px 0;font-size:14px;color:#333333;line-height:1.7;\\">...</p>"],
  "agentic_items": [
    {"company": "<COMPANY TAG>", "headline": "<bold headline>", "body": "<2-3 sentences>"}
  ],
  "news_briefs": [
    {"company": "<COMPANY TAG>", "headline": "<bold headline>", "body": "<2-3 sentences>"}
  ],
  "sources": [
    {"label": "<readable label>", "url": "<full URL>"}
  ]
}

Requirements:
- takeaways: 3-5 items
- deep_dive_body_paragraphs: 4-6 <p> tags, 400-600 words total
- agentic_items: 2-3 items focused on AI agents / agentic AI progress
- news_briefs: 4-6 items covering the remaining top stories
- sources: 8-12 URLs, one per story covered"""

BUILD_SYSTEM = """You are an HTML newsletter builder. You will receive:
1. An HTML template with {{PLACEHOLDER}} tokens
2. Research data as a JSON object
3. A date string

Your job: replace every {{PLACEHOLDER}} with correct HTML content derived from the research.
Return the COMPLETE HTML DOCUMENT and nothing else — no markdown, no explanation, no fences."""

STANDARD_QUERIES = [
    "Anthropic OpenAI Google DeepMind AI news last 31 days",
    "Microsoft Azure AI Foundry Copilot news last 31 days",
    "Meta Nvidia Mistral xAI emerging AI companies news last 31 days",
    "agentic AI agents enterprise deployment announcements last 31 days",
]


def _get_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set in environment")
    return anthropic.Anthropic(api_key=api_key)


def _extract_json(response: anthropic.types.Message) -> dict:
    """Pull the final text block from the response and parse it as JSON."""
    text = ""
    for block in response.content:
        if block.type == "text":
            text = block.text
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.rsplit("```", 1)[0].strip()
    return json.loads(text)


def research_news(
    client: anthropic.Anthropic, extra_topics: list[str] | None = None
) -> dict:
    """Phase 1: run web searches and return structured research JSON."""
    today = date.today().strftime("%B %d, %Y")
    queries = STANDARD_QUERIES.copy()
    if extra_topics:
        queries.extend(extra_topics)

    query_list = "\n".join(f"{i+1}. {q}" for i, q in enumerate(queries))
    user_message = (
        f"Today's date: {today}\n\n"
        f"Run these web searches and synthesize the results:\n{query_list}\n\n"
        "Each query covers multiple companies — run one search per line, do not split them further.\n\n"
        "Choose the deep dive topic as the most strategically significant story you find"
        + (f", or prioritise the first extra topic: '{extra_topics[0]}'" if extra_topics else "")
        + ".\n\nReturn only raw JSON matching the schema in your system prompt."
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8000,
        system=RESEARCH_SYSTEM,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 11}],
        messages=[{"role": "user", "content": user_message}],
        extra_headers={"anthropic-beta": "web-search-2025-03-05"},
    )

    try:
        return _extract_json(response)
    except (json.JSONDecodeError, IndexError, ValueError):
        # Retry once with a follow-up asking for clean JSON
        retry_messages = [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": response.content},
            {
                "role": "user",
                "content": "Your last response was not valid JSON. Return ONLY the raw JSON object — no markdown, no fences, no explanation.",
            },
        ]
        retry_response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8000,
            system=RESEARCH_SYSTEM,
            messages=retry_messages,
        )
        try:
            return _extract_json(retry_response)
        except (json.JSONDecodeError, IndexError, ValueError) as e:
            raise RuntimeError(f"Research phase failed to produce valid JSON after retry: {e}")


def build_html(client: anthropic.Anthropic, research: dict, publish_date: str) -> str:
    """Phase 2: fill the template with research data and return complete HTML."""
    template_text = TEMPLATE_PATH.read_text(encoding="utf-8")

    takeaways_html = ""
    for i, item in enumerate(research.get("takeaways", [])):
        is_last = i == len(research["takeaways"]) - 1
        border = "" if is_last else "border-bottom:1px solid #f0f0f0;"
        takeaways_html += (
            f'<tr><td style="padding:8px 0;{border}">'
            f'<p style="margin:0;font-size:14px;color:#333333;line-height:1.6;">'
            f'&#8226;&nbsp; <strong>{item["label"]}:</strong> {item["text"]}</p>'
            f"</td></tr>\n"
        )

    def _item_html(item: dict, is_last: bool) -> str:
        pb = "padding-bottom:28px;" if is_last else ""
        return (
            f'<tr><td style="padding:0 36px 0 36px;">'
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-top:1px solid #e8e8e8;">'
            f'<tr><td style="padding:16px 0 12px 0;{pb}">'
            f'<span style="display:inline-block;border:1px solid #0078d4;color:#0078d4;font-size:10px;font-weight:bold;padding:2px 8px;border-radius:10px;letter-spacing:1px;">{item["company"]}</span>'
            f'<p style="margin:10px 0 6px 0;font-size:14px;font-weight:bold;color:#0f1f3d;">{item["headline"]}</p>'
            f'<p style="margin:0;font-size:13px;color:#555555;line-height:1.6;">{item["body"]}</p>'
            f"</td></tr></table></td></tr>\n"
        )

    agentic_items = research.get("agentic_items", [])
    agenticwatch_html = "".join(
        _item_html(item, i == len(agentic_items) - 1) for i, item in enumerate(agentic_items)
    )

    news_items = research.get("news_briefs", [])
    news_briefs_html = "".join(
        _item_html(item, i == len(news_items) - 1) for i, item in enumerate(news_items)
    )

    sources_html = "".join(
        f'<tr><td style="padding:3px 0;font-size:12px;color:#555555;">'
        f'<a href="{src["url"]}" style="color:#0078d4;text-decoration:none;">{src["label"]}</a>'
        f"</td></tr>\n"
        for src in research.get("sources", [])
    )

    deep_dive_body = "\n".join(research.get("deep_dive_body_paragraphs", []))

    html = template_text
    html = html.replace("{{DATE}}", publish_date)
    html = html.replace("{{INTRO}}", research.get("intro", ""))
    html = html.replace("{{TAKEAWAYS}}", takeaways_html)
    html = html.replace("{{DEEPDIVE_TITLE}}", research.get("deep_dive_title", ""))
    html = html.replace("{{DEEPDIVE_BODY}}", deep_dive_body)
    html = html.replace("{{AGENTICWATCH}}", agenticwatch_html)
    html = html.replace("{{NEWS_BRIEFS}}", news_briefs_html)
    html = html.replace("{{SOURCES}}", sources_html)

    return html


def generate(
    extra_topics: list[str] | None = None, publish_date: str | None = None
) -> str:
    """
    Orchestrate research + HTML build. Returns complete newsletter HTML string.
    No disk writes — caller receives HTML in memory.
    """
    if publish_date is None:
        publish_date = date.today().strftime("%B %d, %Y")

    client = _get_client()
    research = research_news(client, extra_topics)
    html = build_html(client, research, publish_date)

    remaining = [p for p in ["{{DATE}}", "{{INTRO}}", "{{TAKEAWAYS}}", "{{DEEPDIVE_TITLE}}",
                              "{{DEEPDIVE_BODY}}", "{{AGENTICWATCH}}", "{{NEWS_BRIEFS}}", "{{SOURCES}}"]
                 if p in html]
    if remaining:
        raise RuntimeError(f"HTML generation incomplete — unfilled placeholders: {remaining}")

    return html
