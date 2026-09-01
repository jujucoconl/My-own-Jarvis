"""Gmail integration: fetch recent inbox messages, optionally create drafts."""

from __future__ import annotations

import base64
from datetime import datetime
from email.mime.text import MIMEText
from email.utils import parseaddr, parsedate_to_datetime

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from jarvis.models import Email


def _header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def _extract_body(payload: dict) -> str:
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode(
            "utf-8", errors="replace"
        )
    for part in payload.get("parts", []) or []:
        body = _extract_body(part)
        if body:
            return body
    return ""


def fetch_recent_emails(
    creds: Credentials, account_label: str, max_results: int = 20
) -> list[Email]:
    service = build("gmail", "v1", credentials=creds)
    listing = (
        service.users()
        .messages()
        .list(userId="me", labelIds=["INBOX"], maxResults=max_results)
        .execute()
    )

    emails: list[Email] = []
    for item in listing.get("messages", []):
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=item["id"], format="full")
            .execute()
        )
        headers = msg["payload"].get("headers", [])
        sender_name, sender_email = parseaddr(_header(headers, "From"))
        date_header = _header(headers, "Date")
        try:
            received_at = parsedate_to_datetime(date_header)
        except (TypeError, ValueError):
            received_at = datetime.now().astimezone()

        emails.append(
            Email(
                account_label=account_label,
                provider="gmail",
                message_id=msg["id"],
                sender_name=sender_name or sender_email,
                sender_email=sender_email,
                subject=_header(headers, "Subject") or "(no subject)",
                snippet=msg.get("snippet", ""),
                received_at=received_at,
                is_unread="UNREAD" in msg.get("labelIds", []),
                link=f"https://mail.google.com/mail/u/0/#inbox/{msg['id']}",
                body=_extract_body(msg["payload"])[:4000],
            )
        )
    return emails


def create_gmail_draft(
    creds: Credentials, to: str, subject: str, body: str
) -> str:
    """Creates a Gmail draft reply and returns its draft id (requires gmail.compose scope)."""
    service = build("gmail", "v1", credentials=creds)
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

    draft = (
        service.users()
        .drafts()
        .create(userId="me", body={"message": {"raw": raw}})
        .execute()
    )
    return draft["id"]
