from datetime import datetime

from jarvis.importance import heuristic_triage, triage_emails
from jarvis.models import Email


def _email(**overrides) -> Email:
    base = dict(
        account_label="personal",
        provider="gmail",
        message_id="1",
        sender_name="Jane Doe",
        sender_email="jane@example.com",
        subject="Hello",
        snippet="Just checking in",
        received_at=datetime(2026, 9, 1, 8, 0),
        is_unread=True,
    )
    base.update(overrides)
    return Email(**base)


def test_urgent_keyword_marks_high_importance():
    result = heuristic_triage(_email(subject="Action required: submit your form"))
    assert result.importance == "high"


def test_noreply_sender_marks_low_importance():
    result = heuristic_triage(_email(sender_email="no-reply@service.com", is_unread=True))
    assert result.importance == "low"


def test_unsubscribe_subject_marks_low_importance():
    result = heuristic_triage(_email(subject="50% off - click to unsubscribe"))
    assert result.importance == "low"


def test_plain_unread_email_marks_medium_importance():
    result = heuristic_triage(_email(subject="Notes from lab", is_unread=True))
    assert result.importance == "medium"


def test_read_plain_email_marks_low_importance():
    result = heuristic_triage(_email(subject="Notes from lab", is_unread=False))
    assert result.importance == "low"


def test_triage_emails_without_api_key_uses_heuristic_for_all():
    emails = [_email(message_id=str(i)) for i in range(3)]
    results = triage_emails(emails, api_key=None, model="unused")
    assert len(results) == 3
    assert all(r.reason.startswith("Keyword heuristic") for r in results)
