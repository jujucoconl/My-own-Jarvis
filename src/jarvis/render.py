"""Renders a Briefing as Markdown."""

from __future__ import annotations

from jarvis.models import Briefing, EmailTriage, WeeklyLookahead


def _render_email(t: EmailTriage) -> list[str]:
    e = t.email
    lines = [
        f"- **{e.subject}** - {e.sender_name or e.sender_email} ({e.account_label})",
        f"  - Why it matters: {t.reason}",
        f"  - Next step: {t.suggested_action}",
    ]
    if t.draft_reply:
        lines.append(f"  - Draft reply: _{t.draft_reply}_")
    if e.link:
        lines.append(f"  - [Open email]({e.link})")
    return lines


def render_markdown(briefing: Briefing) -> str:
    lines: list[str] = []
    lines.append(f"# Morning Briefing - {briefing.generated_at.strftime('%A, %B %d %Y %H:%M')}")
    lines.append("")

    lines.append("## Weather & what to wear")
    if briefing.weather and briefing.outfit:
        w = briefing.weather
        lines.append(
            f"{w.condition.capitalize()}, currently {w.temp_now_c:.0f}C "
            f"(feels like {w.feels_like_c:.0f}C), high {w.temp_high_c:.0f}C / "
            f"low {w.temp_low_c:.0f}C, {w.precipitation_probability}% chance of rain."
        )
        lines.append(f"**Wear:** {briefing.outfit.summary}")
        for item in briefing.outfit.items:
            lines.append(f"- {item.category}: {item.subtype} ({item.primary_color})")
        for d in briefing.outfit.details:
            lines.append(f"- {d}")
        if briefing.outfit.missing_piece_note:
            lines.append(f"- _Heads up: {briefing.outfit.missing_piece_note}_")
    else:
        lines.append("_Weather unavailable._")
    lines.append("")

    lines.append("## Today's schedule")
    if briefing.events_today:
        for e in briefing.events_today:
            when = "All day" if e.all_day else f"{e.start.strftime('%H:%M')}-{e.end.strftime('%H:%M')}"
            where = f" @ {e.location}" if e.location else ""
            lines.append(f"- {when}: {e.title}{where}")
    else:
        lines.append("_No events found (or calendar unavailable)._")
    lines.append("")

    if briefing.upcoming_tasks:
        lines.append(f"## Deadlines coming up ({len(briefing.upcoming_tasks)})")
        for t in briefing.upcoming_tasks:
            course = f" ({t.course})" if t.course else ""
            overdue = " - **overdue**" if t.due_at < briefing.generated_at else ""
            lines.append(f"- {t.due_at.strftime('%a %m/%d %H:%M')}: **{t.title}**{course} [{t.priority}]{overdue}")
        lines.append("")

    lines.append("## Downtime suggestions")
    if briefing.downtime:
        for d in briefing.downtime:
            lines.append(
                f"- {d.slot.start.strftime('%H:%M')}-{d.slot.end.strftime('%H:%M')}: {d.suggestion}"
            )
    else:
        lines.append("_No notable free gaps today._")
    lines.append("")

    lines.append(f"## Important emails ({len(briefing.important_emails)})")
    if briefing.important_emails:
        for t in briefing.important_emails:
            lines.extend(_render_email(t))
    else:
        lines.append("_Nothing urgent._")
    lines.append("")

    if briefing.other_emails:
        lines.append(f"## Everything else ({len(briefing.other_emails)})")
        for t in briefing.other_emails:
            e = t.email
            lines.append(
                f"- [{t.importance}] {e.subject} - {e.sender_name or e.sender_email} ({e.account_label})"
            )
        lines.append("")

    if briefing.errors:
        lines.append("## Notes")
        for err in briefing.errors:
            lines.append(f"- {err}")
        lines.append("")

    return "\n".join(lines)


def render_week(lookahead: WeeklyLookahead) -> str:
    lines: list[str] = [f"# Week Ahead - {lookahead.generated_at.strftime('%B %d, %Y')}", ""]

    if lookahead.summary:
        lines.append(lookahead.summary)
        lines.append("")

    for day in lookahead.days:
        lines.append(f"## {day.date.strftime('%A, %B %d')}")
        if not day.events and not day.tasks_due:
            lines.append("_Nothing scheduled._")
        for e in day.events:
            when = "All day" if e.all_day else f"{e.start.strftime('%H:%M')}-{e.end.strftime('%H:%M')}"
            lines.append(f"- {when}: {e.title}")
        for t in day.tasks_due:
            course = f" ({t.course})" if t.course else ""
            lines.append(f"- **Due: {t.title}{course}** [{t.priority}]")
        lines.append("")

    if lookahead.errors:
        lines.append("## Notes")
        for err in lookahead.errors:
            lines.append(f"- {err}")
        lines.append("")

    return "\n".join(lines)
