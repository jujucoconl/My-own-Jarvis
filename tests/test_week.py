from datetime import date, datetime

from jarvis.models import CalendarEvent, DayPlan, Task, WeeklyLookahead
from jarvis.render import render_week


def test_render_week_includes_events_tasks_and_summary():
    event = CalendarEvent(title="ME 270 Exam", start=datetime(2026, 9, 3, 9), end=datetime(2026, 9, 3, 10, 30))
    task = Task(
        task_id="1",
        title="Lab report",
        course="ME 270",
        due_at=datetime(2026, 9, 3, 23, 59),
        notes="",
        priority="high",
        completed=False,
        calendar_event_id="evt123",
        created_at=datetime(2026, 9, 1),
    )
    lookahead = WeeklyLookahead(
        generated_at=datetime(2026, 9, 1, 7, 0),
        days=[
            DayPlan(date=date(2026, 9, 1), events=[], tasks_due=[]),
            DayPlan(date=date(2026, 9, 3), events=[event], tasks_due=[task]),
        ],
        summary="Wednesday is your busiest day - exam plus the lab report is due.",
        errors=["Overdue: Old HW (was due 2026-08-30)"],
    )

    text = render_week(lookahead)

    assert "Week Ahead" in text
    assert "busiest day" in text
    assert "ME 270 Exam" in text
    assert "Lab report" in text
    assert "Nothing scheduled" in text
    assert "Overdue: Old HW" in text
