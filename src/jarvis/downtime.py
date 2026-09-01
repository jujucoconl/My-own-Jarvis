"""Finds free gaps in the day's calendar and suggests what to do with them."""

from __future__ import annotations

from datetime import datetime

from anthropic import Anthropic

from jarvis.ai_json import parse_json_array
from jarvis.models import CalendarEvent, DowntimeSuggestion, FreeSlot, WeatherInfo

_SYSTEM_PROMPT = """You suggest what someone should do with a free gap in their day, given
the weather, who they are, and what's happening right before/after the gap. Be specific and
brief (one sentence) and make the suggestion actually fit the moment - not a generic filler:

- a short gap squeezed between two commitments calls for something low-effort, not a trip
  across town or anything that needs winding down from
- a gap right before something demanding (an exam, an interview, a workout) should probably
  help them arrive ready for it, not tire them out or stress them out
- late-evening gaps should generally be lower-energy than mid-day ones
- prefer an outdoor suggestion when the weather is good and the gap is short; prefer a
  longer at-home/indoor activity for long gaps or bad weather
- lean on their stated interests and who they are, don't just default to "read a book" """


def find_free_slots(
    events: list[CalendarEvent],
    day_start: datetime,
    day_end: datetime,
    min_minutes: int = 30,
) -> list[FreeSlot]:
    busy = sorted(
        (e for e in events if not e.all_day), key=lambda e: e.start
    )

    slots: list[FreeSlot] = []
    cursor = day_start
    for event in busy:
        if event.start > cursor:
            gap = FreeSlot(start=cursor, end=min(event.start, day_end))
            if gap.minutes >= min_minutes:
                slots.append(gap)
        cursor = max(cursor, event.end)
        if cursor >= day_end:
            break

    if cursor < day_end:
        gap = FreeSlot(start=cursor, end=day_end)
        if gap.minutes >= min_minutes:
            slots.append(gap)

    return slots


def _neighbor_context(slot: FreeSlot, events: list[CalendarEvent]) -> str:
    before = next((e.title for e in events if not e.all_day and e.end == slot.start), None)
    after = next((e.title for e in events if not e.all_day and e.start == slot.end), None)
    if before and after:
        return f"between '{before}' and '{after}'"
    if before:
        return f"right after '{before}'"
    if after:
        return f"right before '{after}'"
    return "not next to another event"


def _heuristic_suggestion(slot: FreeSlot, weather: WeatherInfo | None, interests: list[str]) -> str:
    pool = interests or ["a short walk", "reading", "catching up on chores"]
    pick = pool[slot.start.minute % len(pool)]

    good_weather = weather is not None and weather.precipitation_probability < 30 and weather.temp_now_c > 10
    if slot.minutes >= 90:
        return f"You've got {slot.minutes} free minutes - good block for {pick}."
    if good_weather:
        return f"{slot.minutes} min free and decent weather - good time for a quick walk or errand."
    return f"{slot.minutes} min free - maybe {pick}."


def suggest_downtime(
    slots: list[FreeSlot],
    weather: WeatherInfo | None,
    interests: list[str],
    about_me: str = "",
    api_key: str | None = None,
    model: str = "claude-sonnet-5",
    events_today: list[CalendarEvent] | None = None,
) -> list[DowntimeSuggestion]:
    if not slots:
        return []

    if not api_key:
        return [
            DowntimeSuggestion(slot=s, suggestion=_heuristic_suggestion(s, weather, interests))
            for s in slots
        ]

    events_today = events_today or []
    weather_desc = (
        f"{weather.condition}, {weather.temp_now_c:.0f}C now, "
        f"{weather.precipitation_probability}% chance of rain"
        if weather
        else "unknown"
    )
    slot_lines = "\n".join(
        f"[{i}] {s.start.strftime('%a %H:%M')}-{s.end.strftime('%H:%M')} "
        f"({s.minutes} min), {_neighbor_context(s, events_today)}"
        for i, s in enumerate(slots)
    )
    prompt = (
        f"Who they are: {about_me or '(not given)'}\n"
        f"Things they enjoy: {', '.join(interests) if interests else '(none given, use your judgement)'}\n"
        f"Weather: {weather_desc}\n"
        f"Free slots today:\n{slot_lines}\n\n"
        "Return ONLY a JSON array, one object per slot in order, each with keys "
        '"index" and "suggestion" (a single short sentence).'
    )

    try:
        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in response.content if b.type == "text")
        results = {int(r["index"]): r["suggestion"] for r in parse_json_array(text)}
        return [
            DowntimeSuggestion(
                slot=s,
                suggestion=results.get(i) or _heuristic_suggestion(s, weather, interests),
            )
            for i, s in enumerate(slots)
        ]
    except Exception:
        return [
            DowntimeSuggestion(slot=s, suggestion=_heuristic_suggestion(s, weather, interests))
            for s in slots
        ]
