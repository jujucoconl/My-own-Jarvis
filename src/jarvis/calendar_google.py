"""Google Calendar integration (OAuth installed-app flow)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from jarvis.models import CalendarEvent

SCOPES = [
    # Full (not readonly) access - task deadlines get mirrored onto the calendar.
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]


def _cached_token_has_scopes(token_path: Path, required_scopes: list[str]) -> bool:
    """Whether a cached token file already covers every scope we need.

    A token cached before a scope was added to SCOPES (e.g. before calendar
    write access was needed) won't actually have it, even though loading it
    with the new SCOPES list would otherwise look fine locally - Google
    enforces the originally-granted scopes server-side. Catching that here
    forces a fresh consent screen instead of a confusing 403 mid-request.
    """
    try:
        data = json.loads(token_path.read_text())
    except (OSError, json.JSONDecodeError):
        return False
    granted = set(data.get("scopes") or [])
    return set(required_scopes) <= granted


def get_google_credentials(
    credentials_path: Path, token_path: Path
) -> Credentials:
    """Loads cached Google OAuth credentials, refreshing or re-authenticating as needed.

    On first run (or after a required scope is added) this opens a browser
    for the consent screen and caches the resulting token at `token_path` so
    future runs are non-interactive.
    """
    creds: Credentials | None = None
    if token_path.exists() and _cached_token_has_scopes(token_path, SCOPES):
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not credentials_path.exists():
                raise FileNotFoundError(
                    f"Missing Google OAuth client file at {credentials_path}. "
                    "Download it from https://console.cloud.google.com/apis/credentials "
                    "(OAuth client ID -> Desktop app)."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path), SCOPES
            )
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json())

    return creds


def get_events(
    creds: Credentials, time_min: datetime, time_max: datetime
) -> list[CalendarEvent]:
    service = build("calendar", "v3", credentials=creds)
    result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=time_min.isoformat(),
            timeMax=time_max.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    events: list[CalendarEvent] = []
    for item in result.get("items", []):
        start_raw = item["start"].get("dateTime") or item["start"].get("date")
        end_raw = item["end"].get("dateTime") or item["end"].get("date")
        all_day = "date" in item["start"] and "dateTime" not in item["start"]

        events.append(
            CalendarEvent(
                title=item.get("summary", "(no title)"),
                start=datetime.fromisoformat(start_raw),
                end=datetime.fromisoformat(end_raw),
                location=item.get("location"),
                all_day=all_day,
            )
        )
    return events


def get_todays_events(
    creds: Credentials, day_start: datetime, day_end: datetime
) -> list[CalendarEvent]:
    return get_events(creds, day_start, day_end)


def create_calendar_event(
    creds: Credentials,
    title: str,
    start: datetime,
    end: datetime | None = None,
    all_day: bool = True,
    description: str = "",
) -> str:
    """Creates a calendar event and returns its id (for later deletion/updates)."""
    service = build("calendar", "v3", credentials=creds)

    if all_day:
        start_date = start.date()
        end_date = (end.date() if end else start_date)
        if end_date <= start_date:
            end_date = start_date + timedelta(days=1)
        body = {
            "summary": title,
            "description": description,
            "start": {"date": start_date.isoformat()},
            "end": {"date": end_date.isoformat()},
        }
    else:
        end = end or (start + timedelta(hours=1))
        body = {
            "summary": title,
            "description": description,
            "start": {"dateTime": start.isoformat()},
            "end": {"dateTime": end.isoformat()},
        }

    created = service.events().insert(calendarId="primary", body=body).execute()
    return created["id"]


def delete_calendar_event(creds: Credentials, event_id: str) -> None:
    service = build("calendar", "v3", credentials=creds)
    try:
        service.events().delete(calendarId="primary", eventId=event_id).execute()
    except Exception:
        pass  # already gone / never synced - nothing left to clean up
