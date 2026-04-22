"""
app.py — AI Pulse Newsletter web service.

Routes:
  GET  /        Web form to trigger on-demand newsletter generation
  POST /send    Accept form submission, fire generation in background thread, return 202
  POST /auth    Verify access password
  GET  /health  Railway healthcheck

Scheduler:
  APScheduler BackgroundScheduler fires monthly on day=NEWSLETTER_SCHEDULE_DAY (default 1)
  at 08:00 UTC. Gunicorn MUST run with --workers 1 (see railway.json) to prevent the
  scheduler from firing in multiple worker processes simultaneously.
"""

import logging
import os
import threading
from datetime import date, datetime, timezone

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = Flask(__name__)

_job_lock = threading.Lock()
_scheduler = BackgroundScheduler()


# ---------------------------------------------------------------------------
# Telegram notifications
# ---------------------------------------------------------------------------

def _telegram_notify(message: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            timeout=10,
        )
    except Exception as e:
        app.logger.warning(f"Telegram notification failed: {e}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_recipients(raw: str, fallback: str) -> list[str]:
    """Parse a comma-separated email string into a list. Falls back to a single address."""
    emails = [e.strip() for e in raw.replace(";", ",").split(",") if e.strip()]
    return emails if emails else [fallback]


# ---------------------------------------------------------------------------
# Core job
# ---------------------------------------------------------------------------

def run_newsletter_job(
    recipients: list[str] | None = None,
    extra_topics: list[str] | None = None,
    triggered_by: str = "scheduled",
):
    """Generate and send the newsletter. Thread-safe; no shared mutable state."""
    from tools.generate_newsletter import generate
    from tools.send_email import load_config, send

    config = load_config()
    if not recipients:
        recipients = _parse_recipients(config["RECIPIENT_EMAIL"], config["RECIPIENT_EMAIL"])

    html = generate(extra_topics=extra_topics)
    subject = f"AI Pulse | {date.today().strftime('%B %d, %Y')}"
    send(recipients, subject, html, config)
    return recipients


def _scheduled_job():
    app.logger.info("Scheduled newsletter job starting.")
    try:
        recipients = run_newsletter_job(triggered_by="scheduled")
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        _telegram_notify(
            f"✅ <b>AI Pulse Newsletter sent</b>\n"
            f"Trigger: scheduled\n"
            f"Recipients: {', '.join(recipients)}\n"
            f"Time: {ts}"
        )
        app.logger.info("Scheduled newsletter sent successfully.")
    except Exception as e:
        app.logger.error(f"Scheduled newsletter failed: {e}")
        _telegram_notify(f"❌ <b>AI Pulse Newsletter FAILED</b>\nTrigger: scheduled\nError: {e}")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
def index():
    return render_template("index.html")


@app.post("/send")
def trigger_send():
    """
    Fire newsletter generation in a background thread and return 202 immediately.
    Generation takes ~2 minutes due to web_search API calls.
    Returns 409 if a job is already running.
    """
    expected_password = os.environ.get("APP_PASSWORD", "")
    if not expected_password:
        app.logger.warning("APP_PASSWORD is not set — requests are unprotected.")
    elif request.form.get("password", "") != expected_password:
        return jsonify({"status": "forbidden", "message": "Incorrect password."}), 403

    if not _job_lock.acquire(blocking=False):
        return jsonify({
            "status": "busy",
            "message": "A newsletter is already being generated. Check your inbox in a few minutes.",
        }), 409

    config_recipient = os.environ.get("RECIPIENT_EMAIL", "")
    recipients_raw = request.form.get("recipient", "").strip()
    recipients = _parse_recipients(recipients_raw, config_recipient) if recipients_raw else None

    extra_topics_raw = request.form.get("extra_topics", "").strip()
    extra_topics = [t.strip() for t in extra_topics_raw.splitlines() if t.strip()] or None

    def background_task():
        try:
            final_recipients = run_newsletter_job(
                recipients=recipients, extra_topics=extra_topics, triggered_by="on-demand"
            )
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            _telegram_notify(
                f"✅ <b>AI Pulse Newsletter sent</b>\n"
                f"Trigger: on-demand\n"
                f"Recipients: {', '.join(final_recipients)}\n"
                f"Time: {ts}"
            )
            app.logger.info(f"On-demand newsletter sent to {final_recipients}.")
        except Exception as e:
            app.logger.error(f"On-demand newsletter failed: {e}")
            _telegram_notify(f"❌ <b>AI Pulse Newsletter FAILED</b>\nTrigger: on-demand\nError: {e}")
        finally:
            _job_lock.release()

    thread = threading.Thread(target=background_task, daemon=True)
    thread.start()

    return jsonify({
        "status": "accepted",
        "message": "Newsletter generation started — expect delivery in about 2 minutes.",
    }), 202


@app.post("/auth")
def verify_password():
    """Client-side password check — returns 200 if correct, 403 if not."""
    expected_password = os.environ.get("APP_PASSWORD", "")
    if not expected_password or request.form.get("password", "") == expected_password:
        return jsonify({"status": "ok"}), 200
    return jsonify({"status": "forbidden"}), 403


@app.get("/health")
def health():
    return jsonify({"status": "ok"}), 200


# ---------------------------------------------------------------------------
# Scheduler bootstrap
# ---------------------------------------------------------------------------

def start_scheduler():
    schedule_day = os.environ.get("NEWSLETTER_SCHEDULE_DAY", "1")
    _scheduler.add_job(
        _scheduled_job,
        trigger=CronTrigger(day=schedule_day, hour=8, minute=0, timezone="UTC"),
        id="monthly_newsletter",
        replace_existing=True,
    )
    _scheduler.start()
    app.logger.info(f"Scheduler started — newsletter fires on day={schedule_day} of each month at 08:00 UTC.")


# ---------------------------------------------------------------------------
# Start scheduler at import time so Gunicorn workers pick it up.
# --workers 1 in railway.json ensures only one process runs the scheduler.
# ---------------------------------------------------------------------------

start_scheduler()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, use_reloader=False)
