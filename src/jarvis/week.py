"""Builds a 7-day look-ahead: calendar events + tracked deadlines, day by day."""

from __future__ import annotations

from datetime import datetime, timedelta

from anthropic import Anthropic

from jarvis import tasks as tasks_mod
from jarvis.calendar_google import get_events, get_google_credentials
from jarvis.config import AppConfig
from jarvis.models import DayPlan, WeeklyLookahead

_SYSTEM_PROMPT = """You help a busy student plan their week. Given their calendar events
and tracked deadlines for the next 7 days, write a short (3-5 sentence) heads-up: call out
the busiest day(s), which deadline(s) need starting on soonest, and any day that looks like
a good block of time to get ahead. Be concrete and reference actual days/titles - no filler."""


def build_week_lookahead(config: AppConfig) -> WeeklyLookahead:
    secrets = config.secrets
    lookahead = WeeklyLookahead(generated_at=datetime.now().astimezone())

    now = datetime.now().astimezone()
    week_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = week_start + timedelta(days=7)

    events = []
    try:
        creds = get_google_credentials(secrets.google_credentials_path, secrets.google_token_path)
        events = get_events(creds, week_start, week_end)
    except Exception as exc:  # noqa: BLE001
        lookahead.errors.append(f"Google Calendar: {exc}")

    due_tasks = tasks_mod.upcoming_tasks(within_days=7)

    for offset in range(7):
        day_date = (week_start + timedelta(days=offset)).date()
        day_events = [e for e in events if e.start.date() == day_date]
        day_tasks = [t for t in due_tasks if t.due_at.date() == day_date]
        lookahead.days.append(DayPlan(date=day_date, events=day_events, tasks_due=day_tasks))

    overdue = [t for t in due_tasks if t.due_at.date() < week_start.date()]
    if overdue:
        lookahead.errors.append(
            "Overdue: " + "; ".join(f"{t.title} (was due {t.due_at.date()})" for t in overdue)
        )

    if secrets.anthropic_api_key and (events or due_tasks):
        try:
            lookahead.summary = _summarize(lookahead, secrets.anthropic_api_key, secrets.anthropic_model)
        except Exception:  # noqa: BLE001
            lookahead.summary = None

    return lookahead


def _summarize(lookahead: WeeklyLookahead, api_key: str, model: str) -> str:
    lines = []
    for day in lookahead.days:
        parts = [e.title for e in day.events] + [f"DUE: {t.title}" for t in day.tasks_due]
        lines.append(f"{day.date.strftime('%A %m/%d')}: {', '.join(parts) if parts else '(nothing)'}")
    prompt = "\n".join(lines)

    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=300,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in response.content if b.type == "text").strip()
