"""Deadlines/assignments you're tracking, optionally mirrored onto Google Calendar.

Storage lives under tasks/tasks.json - gitignored, it's personal data, created on
first `jarvis task add`.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path

from jarvis.calendar_google import (
    create_calendar_event,
    delete_calendar_event,
    get_google_credentials,
)
from jarvis.config import REPO_ROOT, Secrets
from jarvis.models import Task

TASKS_DIR = REPO_ROOT / "tasks"
TASKS_PATH = TASKS_DIR / "tasks.json"


def _task_to_dict(t: Task) -> dict:
    d = asdict(t)
    d["due_at"] = t.due_at.isoformat()
    d["created_at"] = t.created_at.isoformat()
    return d


def _task_from_dict(d: dict) -> Task:
    d = dict(d)
    d["due_at"] = datetime.fromisoformat(d["due_at"])
    d["created_at"] = datetime.fromisoformat(d["created_at"])
    return Task(**d)


def load_tasks() -> list[Task]:
    if not TASKS_PATH.exists():
        return []
    return [_task_from_dict(d) for d in json.loads(TASKS_PATH.read_text())]


def save_tasks(tasks: list[Task]) -> None:
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    TASKS_PATH.write_text(json.dumps([_task_to_dict(t) for t in tasks], indent=2))


def add_task(
    title: str,
    due_at: datetime,
    course: str = "",
    notes: str = "",
    priority: str = "medium",
    secrets: Secrets | None = None,
    sync_to_calendar: bool = True,
) -> Task:
    calendar_event_id = None
    if sync_to_calendar and secrets is not None:
        try:
            creds = get_google_credentials(secrets.google_credentials_path, secrets.google_token_path)
            description = "\n".join(part for part in (course, notes) if part)
            calendar_event_id = create_calendar_event(
                creds, f"Due: {title}", due_at, all_day=True, description=description
            )
        except Exception:
            calendar_event_id = None  # still tracked locally; calendar sync is best-effort

    task = Task(
        task_id=uuid.uuid4().hex[:10],
        title=title,
        course=course,
        due_at=due_at,
        notes=notes,
        priority=priority,
        completed=False,
        calendar_event_id=calendar_event_id,
        created_at=datetime.now().astimezone(),
    )
    tasks = load_tasks()
    tasks.append(task)
    save_tasks(tasks)
    return task


def complete_task(task_id: str) -> bool:
    tasks = load_tasks()
    for t in tasks:
        if t.task_id == task_id:
            t.completed = True
            save_tasks(tasks)
            return True
    return False


def remove_task(task_id: str, secrets: Secrets | None = None) -> bool:
    tasks = load_tasks()
    remaining = [t for t in tasks if t.task_id != task_id]
    if len(remaining) == len(tasks):
        return False

    removed = next(t for t in tasks if t.task_id == task_id)
    if removed.calendar_event_id and secrets is not None:
        try:
            creds = get_google_credentials(secrets.google_credentials_path, secrets.google_token_path)
            delete_calendar_event(creds, removed.calendar_event_id)
        except Exception:
            pass  # local removal still succeeds even if the calendar side fails

    save_tasks(remaining)
    return True


def upcoming_tasks(
    tasks: list[Task] | None = None, within_days: int = 7, include_completed: bool = False
) -> list[Task]:
    """Tasks due within `within_days` from now - overdue-and-incomplete tasks are
    always included (no lower bound) since those need attention most."""
    tasks = load_tasks() if tasks is None else tasks
    cutoff = datetime.now().astimezone() + timedelta(days=within_days)
    result = [t for t in tasks if (include_completed or not t.completed) and t.due_at <= cutoff]
    return sorted(result, key=lambda t: t.due_at)
