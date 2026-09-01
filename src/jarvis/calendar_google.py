"""Google Calendar integration (OAuth installed-app flow)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from jarvis.models import CalendarEvent

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]


def get_google_credentials(
    credentials_path: Path, token_path: Path
) -> Credentials:
    """Loads cached Google OAuth credentials, refreshing or re-authenticating as needed.

    On first run this opens a browser for the consent screen and caches the
    resulting token at `token_path` so future runs are non-interactive.
    """
    creds: Credentials | None = None
    if token_path.exists():
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


def get_todays_events(
    creds: Credentials, day_start: datetime, day_end: datetime
) -> list[CalendarEvent]:
    service = build("calendar", "v3", credentials=creds)
    result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=day_start.isoformat(),
            timeMax=day_end.isoformat(),
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
