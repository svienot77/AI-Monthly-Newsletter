"""
send_email.py — Send the newsletter HTML via Microsoft Graph API (HTTPS).

Uses OAuth2 refresh-token flow to obtain a short-lived access token, then
calls POST /me/sendMail. Works on Railway (no SMTP port restrictions).

Usage:
    python tools/send_email.py
    python tools/send_email.py --to other@domain.com --subject "Custom subject"

Config: .env
    MICROSOFT_CLIENT_ID
    MICROSOFT_CLIENT_SECRET
    MICROSOFT_TENANT_ID   (use "consumers" for personal Hotmail/Outlook accounts)
    MICROSOFT_REFRESH_TOKEN
    RECIPIENT_EMAIL
    SENDER_NAME           (optional, default: "AI Pulse")
"""

import argparse
import os
import sys
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

HTML_FILE = ROOT / ".tmp" / "newsletter.html"


def load_config():
    required = [
        "MICROSOFT_CLIENT_ID",
        "MICROSOFT_CLIENT_SECRET",
        "MICROSOFT_TENANT_ID",
        "MICROSOFT_REFRESH_TOKEN",
        "RECIPIENT_EMAIL",
    ]
    config = {k: os.getenv(k) for k in required}
    missing = [k for k, v in config.items() if not v]
    if missing:
        raise ValueError(
            f"Missing .env keys: {', '.join(missing)}. Copy .env.example to .env and fill in your credentials."
        )
    config["SENDER_NAME"] = os.getenv("SENDER_NAME", "AI Pulse")
    return config


def _get_access_token(config: dict) -> str:
    """Exchange the refresh token for a short-lived access token."""
    tenant = config["MICROSOFT_TENANT_ID"]
    resp = requests.post(
        f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
        data={
            "grant_type": "refresh_token",
            "client_id": config["MICROSOFT_CLIENT_ID"],
            "client_secret": config["MICROSOFT_CLIENT_SECRET"],
            "refresh_token": config["MICROSOFT_REFRESH_TOKEN"],
            "scope": "https://graph.microsoft.com/Mail.Send offline_access",
        },
        timeout=30,
    )
    if not resp.ok:
        raise RuntimeError(f"Token refresh failed ({resp.status_code}): {resp.text}")
    return resp.json()["access_token"]


def send(to: str | list[str], subject: str, html_body: str, config: dict):
    """Send to one or more recipients. `to` can be a single address or a list."""
    if isinstance(to, str):
        recipients = [e.strip() for e in to.replace(";", ",").split(",") if e.strip()]
    else:
        recipients = [e.strip() for e in to if e.strip()]

    print("[->] Obtaining Microsoft access token ...")
    access_token = _get_access_token(config)

    print(f"[->] Sending email to {', '.join(recipients)} via Microsoft Graph ...")
    resp = requests.post(
        "https://graph.microsoft.com/v1.0/me/sendMail",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json={
            "message": {
                "subject": subject,
                "body": {"contentType": "HTML", "content": html_body},
                "toRecipients": [{"emailAddress": {"address": r}} for r in recipients],
                "from": {
                    "emailAddress": {
                        "name": config["SENDER_NAME"],
                        "address": os.getenv("SENDER_EMAIL", ""),
                    }
                },
            },
            "saveToSentItems": True,
        },
        timeout=30,
    )
    if not resp.ok:
        raise RuntimeError(f"Graph API sendMail failed ({resp.status_code}): {resp.text}")
    print(f"[OK] Newsletter sent to {', '.join(recipients)}")


def main():
    parser = argparse.ArgumentParser(description="Send AI Pulse newsletter via Microsoft Graph")
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
