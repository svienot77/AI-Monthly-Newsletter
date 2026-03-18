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

The newsletter workflow is **AI-orchestrated**: Claude performs steps 1–3 directly, and only step 4 invokes a Python tool.

| Step | Who executes | What happens |
|---|---|---|
| 1. Research | Claude (WebSearch) | 6+ parallel searches, collect 8–12 news items |
| 2. Structure | Claude | Organize into Intro / Key Takeaways / Deep Dive / Briefs / Sources |
| 3. Generate HTML | Claude | Write email-safe HTML → save to `.tmp/newsletter.html` |
| 4. Send | Python tool | `python tools/send_email.py` |

`send_email.py` accepts `--to` and `--subject` flags to override `.env` defaults.

## Required `.env` Keys

```
SMTP_HOST=smtp.gmail.com       # Gmail SMTP (STARTTLS, port 587)
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=xxxx xxxx xxxx xxxx   # Gmail App Password — NOT your Google password
RECIPIENT_EMAIL=recipient@domain.com
SENDER_NAME=AI Pulse                # optional, defaults to "AI Pulse"
```

Gmail requires 2-Step Verification enabled, then an App Password generated at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) (app: Mail).

## How to Run Tools

```bash
python tools/<script_name>.py
```

Install dependencies:

```bash
pip install -r requirements.txt   # python-dotenv only; smtplib is stdlib
```

## Operating Rules

- **Check `tools/` before creating anything new.** Only build a new script if nothing covers the task.
- **Don't overwrite workflows without asking.** Workflows are instructions — update them collaboratively.
- **If a tool uses paid API calls, check before re-running after a failure.**
- **Update the workflow after fixing a bug** — document rate limits, quirks, or new approaches so the fix is permanent.
- **`.tmp/` is disposable.** Never put anything there that can't be regenerated.
