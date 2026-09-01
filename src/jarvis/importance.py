"""Email importance triage and reply/next-step drafting.

Uses Claude when an API key is configured; falls back to a keyword
heuristic otherwise (or if a Claude call fails) so the briefing never
just breaks because of a flaky request.
"""

from __future__ import annotations

import json
import re

from anthropic import Anthropic

from jarvis.models import Email, EmailTriage

_URGENT_WORDS = (
    "urgent",
    "asap",
    "deadline",
    "action required",
    "action needed",
    "overdue",
    "past due",
    "final notice",
    "interview",
    "offer letter",
    "time sensitive",
    "important",
)
_LOW_SENDER_HINTS = ("no-reply", "noreply", "notifications@", "newsletter", "digest")
_LOW_SUBJECT_HINTS = ("unsubscribe", "% off", "sale", "weekly digest")

_BATCH_SIZE = 8

_SYSTEM_PROMPT = """You are an assistant triaging a student's inbox for a morning briefing.
For each email, decide:
- importance: "high" (needs a timely reply/action), "medium" (worth reading, not urgent),
  or "low" (promotional/automated/can skip)
- reason: one short sentence why
- suggested_action: one short sentence on what to do next
- draft_reply: for "high" importance emails that expect a reply, a short (2-4 sentence)
  polite draft reply in the student's voice. Use null for anything that isn't a
  reply-expecting email (receipts, notifications, FYIs, low-importance mail).

Respond with ONLY a JSON array, one object per email in the same order given, each with
exactly the keys: index, importance, reason, suggested_action, draft_reply."""


def heuristic_triage(email: Email) -> EmailTriage:
    subject = email.subject.lower()
    sender = email.sender_email.lower()
    text = f"{subject} {email.snippet.lower()}"

    if any(h in sender for h in _LOW_SENDER_HINTS) or any(
        h in subject for h in _LOW_SUBJECT_HINTS
    ):
        importance = "low"
    elif any(word in text for word in _URGENT_WORDS):
        importance = "high"
    elif email.is_unread:
        importance = "medium"
    else:
        importance = "low"

    action = {
        "high": "Reply soon.",
        "medium": "Review when you have a few minutes.",
        "low": "Skim or archive.",
    }[importance]

    return EmailTriage(
        email=email,
        importance=importance,
        reason="Keyword heuristic (no ANTHROPIC_API_KEY configured, or the AI call failed).",
        suggested_action=action,
        draft_reply=None,
    )


def _build_batch_prompt(emails: list[Email]) -> str:
    lines = []
    for i, e in enumerate(emails):
        body_excerpt = (e.body or e.snippet)[:800].replace("\n", " ")
        lines.append(
            f"[{i}] account={e.account_label} from=\"{e.sender_name} <{e.sender_email}>\" "
            f"subject=\"{e.subject}\" unread={e.is_unread}\n    excerpt: {body_excerpt}"
        )
    return "Emails:\n" + "\n".join(lines)


def _parse_json_array(text: str) -> list[dict]:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON array found in model response.")
    return json.loads(match.group(0))


def _triage_batch(
    client: Anthropic, model: str, emails: list[Email]
) -> list[EmailTriage]:
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_batch_prompt(emails)}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    results = _parse_json_array(text)

    by_index = {int(r["index"]): r for r in results}
    triaged = []
    for i, email in enumerate(emails):
        r = by_index.get(i)
        if not r:
            triaged.append(heuristic_triage(email))
            continue
        triaged.append(
            EmailTriage(
                email=email,
                importance=r.get("importance", "medium"),
                reason=r.get("reason", ""),
                suggested_action=r.get("suggested_action", ""),
                draft_reply=r.get("draft_reply") or None,
            )
        )
    return triaged


def triage_emails(
    emails: list[Email], api_key: str | None, model: str
) -> list[EmailTriage]:
    if not emails:
        return []
    if not api_key:
        return [heuristic_triage(e) for e in emails]

    client = Anthropic(api_key=api_key)
    triaged: list[EmailTriage] = []
    for start in range(0, len(emails), _BATCH_SIZE):
        batch = emails[start : start + _BATCH_SIZE]
        try:
            triaged.extend(_triage_batch(client, model, batch))
        except Exception:
            triaged.extend(heuristic_triage(e) for e in batch)
    return triaged
