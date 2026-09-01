"""Outlook / Microsoft 365 integration via Microsoft Graph (MSAL device-code flow)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import msal
import requests

from jarvis.models import Email

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
SCOPES = ["Mail.Read", "Mail.ReadWrite"]


def _load_cache(cache_path: Path) -> msal.SerializableTokenCache:
    cache = msal.SerializableTokenCache()
    if cache_path.exists():
        cache.deserialize(cache_path.read_text())
    return cache


def get_outlook_token(client_id: str, tenant_id: str, cache_path: Path) -> str:
    """Returns a Graph access token, using a cached refresh token when possible.

    On first run this prints a device-login code/URL to the console (no
    client secret needed - this is a public client / delegated-permissions app).
    """
    cache = _load_cache(cache_path)
    app = msal.PublicClientApplication(
        client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        token_cache=cache,
    )

    accounts = app.get_accounts()
    result = None
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])

    if not result:
        flow = app.initiate_device_flow(scopes=SCOPES)
        if "user_code" not in flow:
            raise RuntimeError(f"Failed to start device flow: {flow}")
        print(flow["message"])  # noqa: T201 - interactive login prompt
        result = app.acquire_token_by_device_flow(flow)

    if "access_token" not in result:
        raise RuntimeError(
            f"Microsoft Graph auth failed: {result.get('error_description', result)}"
        )

    cache_path.write_text(cache.serialize())
    return result["access_token"]


def fetch_recent_emails(
    token: str, account_label: str, max_results: int = 20
) -> list[Email]:
    resp = requests.get(
        f"{GRAPH_BASE}/me/mailFolders/Inbox/messages",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "$top": max_results,
            "$orderby": "receivedDateTime desc",
            "$select": "id,subject,bodyPreview,body,from,receivedDateTime,isRead,webLink",
        },
        timeout=15,
    )
    resp.raise_for_status()

    emails: list[Email] = []
    for item in resp.json().get("value", []):
        sender = (item.get("from") or {}).get("emailAddress", {})
        emails.append(
            Email(
                account_label=account_label,
                provider="outlook",
                message_id=item["id"],
                sender_name=sender.get("name", sender.get("address", "")),
                sender_email=sender.get("address", ""),
                subject=item.get("subject") or "(no subject)",
                snippet=item.get("bodyPreview", ""),
                received_at=datetime.fromisoformat(
                    item["receivedDateTime"].replace("Z", "+00:00")
                ),
                is_unread=not item.get("isRead", True),
                link=item.get("webLink"),
                body=(item.get("body", {}).get("content", ""))[:4000],
            )
        )
    return emails


def create_outlook_draft_reply(token: str, message_id: str, comment: str) -> None:
    """Creates a draft reply in Outlook (requires Mail.ReadWrite scope)."""
    resp = requests.post(
        f"{GRAPH_BASE}/me/messages/{message_id}/createReply",
        headers={"Authorization": f"Bearer {token}"},
        json={"comment": comment},
        timeout=15,
    )
    resp.raise_for_status()
