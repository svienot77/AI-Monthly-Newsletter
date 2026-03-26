# Workflow: AI Pulse Newsletter

## Objective
Research recent AI news, write a professional HTML newsletter, and deliver it by email to the recipient defined in `.env`.

## Inputs
- **Topic** (required): The main subject for the deep-dive article. Provided by the user at runtime.
- **Date range**: Last 31 days (fixed — this is always a monthly newsletter).

## Target audience
Microsoft Support leadership board — senior, deeply technical, engineering-connected. Write with authority and precision. No fluff.

## Editorial balance

**Strategic > Technical.** Cover both dimensions, but maintain a clear hierarchy:
- **Strategic lens (primary):** business impact, competitive dynamics, adoption signals, organizational implications
- **Technical lens (secondary):** how it works at a high level — enough to be credible and actionable, not a deep tutorial

In practice: each item should answer "so what does this mean for how AI is being used / deployed / competed over?" first, and "how does it technically work?" briefly if relevant. A one-sentence technical callout per item is sufficient unless the topic is inherently technical (e.g., a new model architecture), in which case 2–3 sentences max.

---

## Steps

### Step 1 — Research

Run **11 parallel searches** covering:
1. `Anthropic news last 31 days`
2. `Google DeepMind AI news last 31 days`
3. `Meta AI news last 31 days`
4. `Microsoft AI Foundry news last 31 days`
5. `Microsoft Copilot AI news last 31 days`
6. `Perplexity AI news last 31 days`
7. `OpenAI AI news last 31 days`
8. `Nvidia AI news last 31 days`
9. `{TOPIC} AI last 31 days` ← user-specified topic
10. `agentic AI agents progress announcements last 31 days`
11. `AI agents enterprise strategy deployment last 31 days`

Also run 1–2 searches for notable emerging AI companies (e.g., Mistral, xAI, Cohere, Stability AI, Runway).

**Collect:**
- 10–14 distinct news items total
- For each item: headline, 2–3 sentence summary, source URL, publication date
- Flag the most significant item as a candidate for the deep-dive (usually the user topic)
- Ensure **at least 2 items** specifically cover agentic AI progress (new frameworks, agent releases, multi-agent strategies, enterprise deployments)

---

### Step 2 — Structure content

Organize into these sections:

| Section | Content | Length |
|---|---|---|
| **Intro / Editorial** | 2–3 sentences framing the month's theme | ~60 words |
| **Key Takeaways** | 3–5 bullet points, highest-signal items | ~100 words |
| **Deep Dive** | Full analysis of the user-specified topic. Lead with strategic framing (2/3 of content), close with a "Under the Hood" paragraph briefly explaining the technical mechanism (1/3) | 400–600 words |
| **Agentic AI Watch** | Dedicated section covering the month's most notable progress in agentic AI — new agent frameworks, multi-agent architectures, enterprise adoption moves, and strategic positioning by major players. Lead with strategy, include a brief technical note where relevant. | 200–300 words |
| **News Briefs** | 4–6 shorter items, 2–3 sentences each. Emphasize strategic angle; add a brief technical note only when it meaningfully changes the picture | ~300 words |
| **Sources** | All cited URLs with labels | list |

Total target: ~1,200–1,500 words → ~10–12 min read.

---

### Step 3 — Generate HTML

**Always use `tools/newsletter_template.html` as the base.** Read the file, then replace each `{{PLACEHOLDER}}` with the generated content. Never redesign the layout or change any inline styles — the template is the canonical look and feel.

| Placeholder | What to fill in |
|---|---|
| `{{DATE}}` | e.g. `March 17, 2026` |
| `{{INTRO}}` | 2–3 sentence editorial paragraph |
| `{{TAKEAWAYS}}` | One `<tr>` block per bullet (last one omits `border-bottom`) |
| `{{DEEPDIVE_TITLE}}` | Title of the deep-dive article |
| `{{DEEPDIVE_BODY}}` | Intro paragraph + sub-sections (`<p>` tags only, inline styles preserved) |
| `{{AGENTICWATCH}}` | One `<tr>` block per agentic AI item (same pattern as News Briefs) |
| `{{NEWS_BRIEFS}}` | One `<tr>` block per brief (last one uses `padding-bottom:28px`) |
| `{{SOURCES}}` | One `<tr>` per source link |

The repeat-block comment inside each section shows the exact HTML pattern to follow.

Save the completed file to: `.tmp/newsletter.html`

---

### Step 4 — Send

```bash
python tools/send_email.py
```

To override recipient or subject:
```bash
python tools/send_email.py --to other@domain.com --subject "AI Pulse | Special Edition"
```

---

## Error handling

| Error | Action |
|---|---|
| SMTP auth failure (535) | Gmail requires an **App Password**, not your regular password. Enable 2-Step Verification at myaccount.google.com, then generate an App Password at myaccount.google.com/apppasswords (app: Mail). Paste the 16-char password (spaces included or stripped) into `SMTP_PASSWORD`. |
| SMTP auth failure (credentials wrong) | Verify `SMTP_USER` is your full Gmail address and `SMTP_PASSWORD` is the App Password, not your Google account password. |
| `.tmp/newsletter.html` not found | Re-run Step 3. |
| Search returns stale results | Narrow the date range in the query (e.g., add `site:techcrunch.com OR site:theverge.com`). |
| Missing news for a company | Note it in the intro ("quiet week for X") — don't fabricate. |

## Dependencies

```bash
pip install python-dotenv
```

No other packages required (`smtplib` is stdlib).
