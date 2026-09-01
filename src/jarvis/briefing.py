"""Orchestrates weather, calendar, and email into a single morning Briefing."""

from __future__ import annotations

from datetime import datetime, time

from jarvis import downtime as downtime_mod
from jarvis import email_gmail, email_outlook, outfit, wardrobe as wardrobe_mod
from jarvis import tasks as tasks_mod
from jarvis import weather as weather_mod
from jarvis.calendar_google import get_google_credentials, get_todays_events
from jarvis.config import AppConfig
from jarvis.importance import triage_emails
from jarvis.models import Briefing, Email

# How many days ahead the daily brief peeks for a "coming up" nudge - the
# fuller picture lives in `jarvis week` (7 days).
UPCOMING_TASK_WINDOW_DAYS = 3


def _parse_hhmm(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def _today_window(wake_time: str, sleep_time: str) -> tuple[datetime, datetime]:
    now = datetime.now().astimezone()
    start = now.replace(
        hour=_parse_hhmm(wake_time).hour,
        minute=_parse_hhmm(wake_time).minute,
        second=0,
        microsecond=0,
    )
    end = now.replace(
        hour=_parse_hhmm(sleep_time).hour,
        minute=_parse_hhmm(sleep_time).minute,
        second=0,
        microsecond=0,
    )
    return start, end


def build_briefing(config: AppConfig) -> Briefing:
    user, secrets = config.user, config.secrets
    briefing = Briefing(generated_at=datetime.now().astimezone(), weather=None, outfit=None)

    try:
        weather_info = weather_mod.get_weather(user.location)
        briefing.weather = weather_info
    except Exception as exc:  # noqa: BLE001 - keep the rest of the briefing working
        briefing.errors.append(f"Weather: {exc}")
        weather_info = None

    google_creds = None
    day_start, day_end = _today_window(user.wake_time, user.sleep_time)
    try:
        google_creds = get_google_credentials(
            secrets.google_credentials_path, secrets.google_token_path
        )
        briefing.events_today = get_todays_events(google_creds, day_start, day_end)
    except Exception as exc:  # noqa: BLE001
        briefing.errors.append(f"Google Calendar: {exc}")

    if weather_info:
        try:
            wardrobe_items = wardrobe_mod.load_wardrobe()
            style_profile = wardrobe_mod.load_style_profile()
            event_titles = [e.title for e in briefing.events_today]
            briefing.outfit = outfit.choose_outfit(
                weather_info, wardrobe_items, style_profile, user.style_notes, event_titles,
                secrets.anthropic_api_key, secrets.anthropic_model,
            )
        except Exception as exc:  # noqa: BLE001
            briefing.errors.append(f"Outfit: {exc}")

    if briefing.events_today or google_creds:
        free_slots = downtime_mod.find_free_slots(
            briefing.events_today, day_start, day_end, user.min_downtime_minutes
        )
        briefing.downtime = downtime_mod.suggest_downtime(
            free_slots, weather_info, user.interests, user.about_me,
            secrets.anthropic_api_key, secrets.anthropic_model,
            events_today=briefing.events_today,
        )

    all_emails: list[Email] = []
    ms_token = None
    for account in user.email_accounts:
        try:
            if account.provider == "gmail":
                if google_creds is None:
                    google_creds = get_google_credentials(
                        secrets.google_credentials_path, secrets.google_token_path
                    )
                all_emails.extend(
                    email_gmail.fetch_recent_emails(
                        google_creds, account.label, user.max_emails_per_account
                    )
                )
            elif account.provider == "outlook":
                if ms_token is None:
                    if not secrets.ms_client_id:
                        raise RuntimeError("MS_CLIENT_ID is not set in .env")
                    ms_token = email_outlook.get_outlook_token(
                        secrets.ms_client_id, secrets.ms_tenant_id, secrets.ms_token_cache_path
                    )
                all_emails.extend(
                    email_outlook.fetch_recent_emails(
                        ms_token, account.label, user.max_emails_per_account
                    )
                )
            else:
                briefing.errors.append(
                    f"Email account '{account.label}': unknown provider '{account.provider}'"
                )
        except Exception as exc:  # noqa: BLE001
            briefing.errors.append(f"Email account '{account.label}': {exc}")

    if all_emails:
        triaged = triage_emails(all_emails, secrets.anthropic_api_key, secrets.anthropic_model)
        briefing.important_emails = [t for t in triaged if t.importance == "high"]
        briefing.other_emails = [t for t in triaged if t.importance != "high"]

    try:
        briefing.upcoming_tasks = tasks_mod.upcoming_tasks(within_days=UPCOMING_TASK_WINDOW_DAYS)
    except Exception as exc:  # noqa: BLE001
        briefing.errors.append(f"Tasks: {exc}")

    return briefing
