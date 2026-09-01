from datetime import datetime, timedelta

from jarvis.downtime import find_free_slots, suggest_downtime
from jarvis.models import CalendarEvent


def _dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 9, 1, hour, minute)


def test_no_events_gives_one_slot_for_the_whole_day():
    slots = find_free_slots([], _dt(7), _dt(23))
    assert len(slots) == 1
    assert slots[0].minutes == (23 - 7) * 60


def test_events_split_the_day_into_gaps():
    events = [
        CalendarEvent(title="Class", start=_dt(9), end=_dt(10, 30)),
        CalendarEvent(title="Lab", start=_dt(13), end=_dt(15)),
    ]
    slots = find_free_slots(events, _dt(7), _dt(23), min_minutes=30)
    # gap before class, between class/lab, and after lab
    assert len(slots) == 3
    assert slots[0].start == _dt(7)
    assert slots[0].end == _dt(9)
    assert slots[1].start == _dt(10, 30)
    assert slots[1].end == _dt(13)
    assert slots[2].start == _dt(15)
    assert slots[2].end == _dt(23)


def test_short_gaps_are_dropped_below_min_minutes():
    events = [
        CalendarEvent(title="A", start=_dt(9), end=_dt(10)),
        CalendarEvent(title="B", start=_dt(10, 10), end=_dt(11)),
    ]
    slots = find_free_slots(events, _dt(9), _dt(11), min_minutes=30)
    assert slots == []


def test_all_day_events_are_ignored_for_free_slots():
    events = [CalendarEvent(title="Holiday", start=_dt(0), end=_dt(0), all_day=True)]
    slots = find_free_slots(events, _dt(7), _dt(23))
    assert len(slots) == 1


def test_suggest_downtime_without_api_key_uses_heuristic_and_covers_every_slot():
    events = [CalendarEvent(title="Class", start=_dt(9), end=_dt(10))]
    slots = find_free_slots(events, _dt(7), _dt(20), min_minutes=30)
    suggestions = suggest_downtime(slots, None, ["reading", "gym"], api_key=None, model="unused")
    assert len(suggestions) == len(slots)
    assert all(s.suggestion for s in suggestions)
