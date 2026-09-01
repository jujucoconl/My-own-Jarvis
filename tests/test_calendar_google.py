import json

from jarvis.calendar_google import SCOPES, _cached_token_has_scopes


def test_missing_token_file_has_no_scopes(tmp_path):
    assert _cached_token_has_scopes(tmp_path / "missing.json", SCOPES) is False


def test_token_with_all_required_scopes(tmp_path):
    token_path = tmp_path / "token.json"
    token_path.write_text(json.dumps({"scopes": SCOPES}))
    assert _cached_token_has_scopes(token_path, SCOPES) is True


def test_token_missing_a_newly_added_scope(tmp_path):
    token_path = tmp_path / "token.json"
    old_scopes = [s for s in SCOPES if "calendar" not in s] + [
        "https://www.googleapis.com/auth/calendar.readonly"
    ]
    token_path.write_text(json.dumps({"scopes": old_scopes}))
    assert _cached_token_has_scopes(token_path, SCOPES) is False


def test_malformed_token_file_treated_as_missing_scopes(tmp_path):
    token_path = tmp_path / "token.json"
    token_path.write_text("not json")
    assert _cached_token_has_scopes(token_path, SCOPES) is False
