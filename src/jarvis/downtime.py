"""Finds free gaps in the day's calendar and suggests what to do with them."""

from __future__ import annotations

import json
import re
from datetime import datetime

from anthropic import Anthropic

from jarvis.models import CalendarEvent, DowntimeSuggestion, FreeSlot, WeatherInfo

_SYSTEM_PROMPT = """You suggest what a busy engineering student should do with a free
gap in their day, given the weather and a list of things they enjoy. Be specific and
brief (one sentence). Prefer an outdoor suggestion when the weather is good and the
gap is short; prefer a longer at-home/indoor activity for long gaps or bad weather."""


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


def _heuristic_suggestion(slot: FreeSlot, weather: WeatherInfo | None, interests: list[str]) -> str:
    pool = interests or ["a short walk", "reading", "catching up on chores"]
    pick = pool[slot.start.minute % len(pool)]

    good_weather = weather is not None and weather.precipitation_probability < 30 and weather.temp_now_c > 10
    if slot.minutes >= 90:
        return f"You've got {slot.minutes} free minutes - good block for {pick}."
    if good_weather:
        return f"{slot.minutes} min free and decent weather - good time for a quick walk or errand."
    return f"{slot.minutes} min free - maybe {pick}."


def _parse_json_array(text: str) -> list[dict]:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON array found in model response.")
    return json.loads(match.group(0))


def suggest_downtime(
    slots: list[FreeSlot],
    weather: WeatherInfo | None,
    interests: list[str],
    api_key: str | None,
    model: str,
) -> list[DowntimeSuggestion]:
    if not slots:
        return []

    if not api_key:
        return [
            DowntimeSuggestion(slot=s, suggestion=_heuristic_suggestion(s, weather, interests))
            for s in slots
        ]

    weather_desc = (
        f"{weather.condition}, {weather.temp_now_c:.0f}C now, "
        f"{weather.precipitation_probability}% chance of rain"
        if weather
        else "unknown"
    )
    slot_lines = "\n".join(
        f"[{i}] {s.start.strftime('%H:%M')}-{s.end.strftime('%H:%M')} ({s.minutes} min)"
        for i, s in enumerate(slots)
    )
    prompt = (
        f"Weather: {weather_desc}\n"
        f"Interests: {', '.join(interests) if interests else '(none given, use your judgement)'}\n"
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
        results = {int(r["index"]): r["suggestion"] for r in _parse_json_array(text)}
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
