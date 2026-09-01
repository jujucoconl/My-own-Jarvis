"""Shared data types passed between Jarvis's modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class WeatherInfo:
    condition: str  # short description, e.g. "light rain"
    temp_now_c: float
    temp_high_c: float
    temp_low_c: float
    feels_like_c: float
    precipitation_probability: int  # 0-100
    wind_kph: float
    is_daytime: bool = True


@dataclass
class WardrobeItem:
    item_id: str
    image_path: str  # relative to the wardrobe/ directory
    category: str  # top | bottom | outerwear | dress | shoes | accessory
    subtype: str  # e.g. "flannel button-up"
    primary_color: str
    secondary_colors: list[str]
    warmth: int  # 1 (very light) - 5 (heavy winter)
    formality: str  # casual | smart_casual | formal | athletic
    rain_ok: bool
    style_tags: list[str]
    description: str
    added_at: datetime


@dataclass
class StyleProfile:
    summary: str
    generated_at: datetime
    based_on_item_count: int


@dataclass
class OutfitSuggestion:
    summary: str  # one-line takeaway, e.g. "Light jacket + umbrella"
    details: list[str] = field(default_factory=list)
    items: list[WardrobeItem] = field(default_factory=list)
    missing_piece_note: str | None = None


@dataclass
class CalendarEvent:
    title: str
    start: datetime
    end: datetime
    location: str | None = None
    all_day: bool = False


@dataclass
class FreeSlot:
    start: datetime
    end: datetime

    @property
    def minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)


@dataclass
class DowntimeSuggestion:
    slot: FreeSlot
    suggestion: str


@dataclass
class Email:
    account_label: str
    provider: str  # "gmail" | "outlook"
    message_id: str
    sender_name: str
    sender_email: str
    subject: str
    snippet: str
    received_at: datetime
    is_unread: bool
    link: str | None = None
    body: str = ""


@dataclass
class EmailTriage:
    email: Email
    importance: str  # "high" | "medium" | "low"
    reason: str
    suggested_action: str
    draft_reply: str | None = None


@dataclass
class Task:
    task_id: str
    title: str
    course: str  # optional context, e.g. "ME 270" - blank if not given
    due_at: datetime
    notes: str
    priority: str  # low | medium | high
    completed: bool
    calendar_event_id: str | None  # Google Calendar event this deadline is mirrored to
    created_at: datetime


@dataclass
class DayPlan:
    date: date
    events: list[CalendarEvent] = field(default_factory=list)
    tasks_due: list[Task] = field(default_factory=list)


@dataclass
class WeeklyLookahead:
    generated_at: datetime
    days: list[DayPlan] = field(default_factory=list)
    summary: str | None = None
    errors: list[str] = field(default_factory=list)


@dataclass
class Briefing:
    generated_at: datetime
    weather: WeatherInfo | None
    outfit: OutfitSuggestion | None
    events_today: list[CalendarEvent] = field(default_factory=list)
    downtime: list[DowntimeSuggestion] = field(default_factory=list)
    important_emails: list[EmailTriage] = field(default_factory=list)
    other_emails: list[EmailTriage] = field(default_factory=list)
    upcoming_tasks: list[Task] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
