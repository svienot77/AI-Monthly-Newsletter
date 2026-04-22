"""
app.py — AI Pulse Newsletter web service.

Routes:
  GET  /        Web form to trigger on-demand newsletter generation
  POST /send    Accept form submission, fire generation in background thread, return 202
  GET  /health  Railway healthcheck

Scheduler:
  APScheduler BackgroundScheduler fires monthly on day=NEWSLETTER_SCHEDULE_DAY (default 1)
  at 08:00 UTC. Gunicorn MUST run with --workers 1 (see railway.json) to prevent the
  scheduler from firing in multiple worker processes simultaneously.
"""

import logging
import os
import threading
from datetime import date

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
# Core job
# ---------------------------------------------------------------------------

def run_newsletter_job(recipient_override: str | None = None, extra_topics: list[str] | None = None):
    """Generate and send the newsletter. Thread-safe; no shared mutable state."""
    from tools.generate_newsletter import generate
    from tools.send_email import load_config, send

    config = load_config()
    html = generate(extra_topics=extra_topics)
    recipient = recipient_override or config["RECIPIENT_EMAIL"]
    subject = f"AI Pulse | {date.today().strftime('%B %d, %Y')}"
    send(recipient, subject, html, config)


def _scheduled_job():
    app.logger.info("Scheduled newsletter job starting.")
    try:
        run_newsletter_job()
        app.logger.info("Scheduled newsletter sent successfully.")
    except Exception as e:
        app.logger.error(f"Scheduled newsletter failed: {e}")


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

    recipient = request.form.get("recipient", "").strip() or None
    extra_topics_raw = request.form.get("extra_topics", "").strip()
    extra_topics = [t.strip() for t in extra_topics_raw.splitlines() if t.strip()] or None

    def background_task():
        try:
            run_newsletter_job(recipient_override=recipient, extra_topics=extra_topics)
            app.logger.info(f"On-demand newsletter sent to {recipient or 'default recipient'}.")
        except Exception as e:
            app.logger.error(f"On-demand newsletter failed: {e}")
        finally:
            _job_lock.release()

    thread = threading.Thread(target=background_task, daemon=True)
    thread.start()

    return jsonify({
        "status": "accepted",
        "message": "Newsletter generation started — expect delivery in about 2 minutes.",
    }), 202


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
