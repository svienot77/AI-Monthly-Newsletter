"""
send_email.py — Send the newsletter HTML file via Outlook / Office 365 SMTP.

Usage:
    python tools/send_email.py
    python tools/send_email.py --to other@domain.com --subject "Custom subject"

Reads:  .tmp/newsletter.html
Config: .env (SMTP_USER, SMTP_PASSWORD, SMTP_HOST, SMTP_PORT, RECIPIENT_EMAIL, SENDER_NAME)
"""

import argparse
import os
import smtplib
import sys
from datetime import date
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

HTML_FILE = ROOT / ".tmp" / "newsletter.html"


def load_config():
    required = ["SMTP_USER", "SMTP_PASSWORD", "SMTP_HOST", "SMTP_PORT", "RECIPIENT_EMAIL"]
    config = {k: os.getenv(k) for k in required}
    missing = [k for k, v in config.items() if not v]
    if missing:
        raise ValueError(f"Missing .env keys: {', '.join(missing)}. Copy .env.example to .env and fill in your credentials.")
    config["SENDER_NAME"] = os.getenv("SENDER_NAME", "AI Pulse")
    return config


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def send(to: str, subject: str, html_body: str, config: dict):
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = f"{config['SENDER_NAME']} <{config['SMTP_USER']}>"
    msg["To"] = to
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    attachment = MIMEApplication(html_body.encode("utf-8"), Name="newsletter.html")
    attachment["Content-Disposition"] = 'attachment; filename="newsletter.html"'
    msg.attach(attachment)

    port = int(config["SMTP_PORT"])
    print(f"[->] Connecting to {config['SMTP_HOST']}:{port} ...")
    if port == 465:
        # SSL from the start (required on Railway where port 587/STARTTLS is blocked)
        import ssl
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(config["SMTP_HOST"], port, context=ctx) as server:
            server.login(config["SMTP_USER"], config["SMTP_PASSWORD"])
            server.sendmail(config["SMTP_USER"], to, msg.as_string())
    else:
        # STARTTLS (port 587, works locally)
        with smtplib.SMTP(config["SMTP_HOST"], port) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(config["SMTP_USER"], config["SMTP_PASSWORD"])
            server.sendmail(config["SMTP_USER"], to, msg.as_string())

    print(f"[OK] Newsletter sent to {to}")


def main():
    parser = argparse.ArgumentParser(description="Send AI Pulse newsletter via Outlook SMTP")
    parser.add_argument("--to", help="Override recipient email from .env")
    parser.add_argument("--subject", help="Override email subject")
    args = parser.parse_args()

    config = load_config()

    if not HTML_FILE.exists():
        print(f"[ERROR] Newsletter HTML not found at {HTML_FILE}")
        print("        Run the newsletter workflow first to generate it.")
        sys.exit(1)

    html_body = HTML_FILE.read_text(encoding="utf-8")
    recipient = args.to or config["RECIPIENT_EMAIL"]
    subject = args.subject or f"AI Pulse | {date.today().strftime('%B %d, %Y')}"

    send(recipient, subject, html_body, config)


if __name__ == "__main__":
    main()
