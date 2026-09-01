from datetime import datetime

from jarvis.models import (
    Briefing,
    CalendarEvent,
    DowntimeSuggestion,
    Email,
    EmailTriage,
    FreeSlot,
    OutfitSuggestion,
    WeatherInfo,
)
from jarvis.render import render_markdown


def test_render_includes_all_sections():
    weather = WeatherInfo(
        condition="clear sky",
        temp_now_c=20,
        temp_high_c=22,
        temp_low_c=15,
        feels_like_c=19,
        precipitation_probability=10,
        wind_kph=8,
    )
    outfit = OutfitSuggestion(summary="T-shirt, light layers optional", details=["Bring a light jacket for the evening."])
    event = CalendarEvent(title="ME 270", start=datetime(2026, 9, 1, 9), end=datetime(2026, 9, 1, 10))
    slot = FreeSlot(start=datetime(2026, 9, 1, 10), end=datetime(2026, 9, 1, 12))
    downtime = DowntimeSuggestion(slot=slot, suggestion="Good block for a workout.")
    email = Email(
        account_label="personal",
        provider="gmail",
        message_id="1",
        sender_name="Professor Smith",
        sender_email="smith@purdue.edu",
        subject="Assignment deadline moved",
        snippet="...",
        received_at=datetime(2026, 9, 1, 7),
        is_unread=True,
        link="https://mail.google.com/mail/u/0/#inbox/1",
    )
    triage = EmailTriage(
        email=email,
        importance="high",
        reason="Deadline change from professor.",
        suggested_action="Reply confirming you saw it.",
        draft_reply="Thanks for the update, I'll plan accordingly.",
    )

    briefing = Briefing(
        generated_at=datetime(2026, 9, 1, 7, 0),
        weather=weather,
        outfit=outfit,
        events_today=[event],
        downtime=[downtime],
        important_emails=[triage],
        other_emails=[],
        errors=["Outlook: not configured"],
    )

    text = render_markdown(briefing)

    assert "Morning Briefing" in text
    assert "T-shirt" in text
    assert "ME 270" in text
    assert "workout" in text
    assert "Assignment deadline moved" in text
    assert "Draft reply" in text
    assert "Outlook: not configured" in text
