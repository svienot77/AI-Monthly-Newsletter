# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Newsletter Demo — a WAT framework project (Workflows, Agents, Tools) for building newsletter automation. AI handles orchestration; deterministic Python scripts handle execution.

## Architecture: WAT Framework

```
workflows/      # Markdown SOPs — read these first before any task
tools/          # Python scripts for deterministic execution (API calls, transforms, I/O)
.tmp/           # Disposable intermediates (scraped data, exports). Never commit.
.env            # All credentials and API keys live here exclusively
```

**Execution model:**
1. Read the relevant `workflows/*.md` to understand the task
2. Identify which `tools/*.py` scripts to call and in what order
3. Run the tools; handle errors by fixing the script, not by retrying blindly
4. Final outputs go to cloud services (Google Sheets, Slides, etc.) — not local files

## Current Workflow: Newsletter (`workflows/newsletter.md`)

Two modes of operation:

**Interactive (Claude Code session):** Claude performs steps 1–3 directly, then calls `python tools/send_email.py`.

**Automated (web service / Railway):** `tools/generate_newsletter.py` calls the Anthropic API with the `web_search` tool, builds the HTML in-memory, and `app.py` delivers it via `tools/send_email.py`.

| Step | Interactive | Automated |
|---|---|---|
| 1. Research | Claude (WebSearch) | `generate_newsletter.py` → Anthropic API + web_search |
| 2. Structure | Claude | Anthropic API response (JSON) |
| 3. Generate HTML | Claude → `.tmp/newsletter.html` | Python string substitution (in-memory) |
| 4. Send | `python tools/send_email.py` | `app.py` calls `send_email.send()` |

`send_email.py` accepts `--to` and `--subject` flags to override `.env` defaults.

## Web Service (`app.py`)

Flask app with APScheduler. Start locally: `python app.py` → <http://localhost:5000>

**IMPORTANT:** Gunicorn must run with `--workers 1` (enforced in `railway.json`). This is intentional — APScheduler runs in-process and would fire the monthly job N times with N workers.

Newsletter HTML is passed in-memory between generation and sending. Nothing is written to `.tmp/` in the automated code path.

## Required `.env` Keys

```
ANTHROPIC_API_KEY=sk-ant-...        # Required for automated generation
SMTP_HOST=smtp.gmail.com            # Gmail SMTP (STARTTLS, port 587)
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=xxxx xxxx xxxx xxxx   # Gmail App Password — NOT your Google password
RECIPIENT_EMAIL=recipient@domain.com
SENDER_NAME=AI Pulse                # optional, defaults to "AI Pulse"
NEWSLETTER_SCHEDULE_DAY=1           # Day of month for scheduled send (default: 1)
```

Gmail requires 2-Step Verification enabled, then an App Password generated at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) (app: Mail).

See `.env.example` for the full template.

## How to Run Tools

```bash
python tools/<script_name>.py
```

Install dependencies:

```bash
pip install -r requirements.txt   # flask, gunicorn, apscheduler, anthropic, python-dotenv
```

## Operating Rules

- **Check `tools/` before creating anything new.** Only build a new script if nothing covers the task.
- **Don't overwrite workflows without asking.** Workflows are instructions — update them collaboratively.
- **If a tool uses paid API calls, check before re-running after a failure.**
- **Update the workflow after fixing a bug** — document rate limits, quirks, or new approaches so the fix is permanent.
- **`.tmp/` is disposable.** Never put anything there that can't be regenerated.
