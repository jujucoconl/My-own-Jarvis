import subprocess
from pathlib import Path

import pytest

from jarvis import schedule
from jarvis.schedule import _MARKER_END, _MARKER_START, _replace_marker_block, build_cron_line


def test_build_cron_line_has_correct_time_and_days():
    line = build_cron_line("06:45", "1-5", Path("/tmp/briefings"))
    assert line.startswith("45 6 * * 1-5 ")
    assert "jarvis.cli brief" in line
    assert "/tmp/briefings" in line


def test_replace_marker_block_appends_when_nothing_installed():
    result = _replace_marker_block(["0 9 * * * some-other-job"], "45 6 * * 1-5 jarvis brief")
    assert result == [
        "0 9 * * * some-other-job",
        _MARKER_START,
        "45 6 * * 1-5 jarvis brief",
        _MARKER_END,
    ]


def test_replace_marker_block_replaces_existing_without_duplicating():
    existing = [
        "0 9 * * * some-other-job",
        _MARKER_START,
        "45 6 * * 1-5 old jarvis line",
        _MARKER_END,
    ]
    result = _replace_marker_block(existing, "0 7 * * 1-5 new jarvis line")
    assert result == [
        "0 9 * * * some-other-job",
        _MARKER_START,
        "0 7 * * 1-5 new jarvis line",
        _MARKER_END,
    ]


def test_replace_marker_block_removes_when_new_line_is_none():
    existing = [
        "0 9 * * * some-other-job",
        _MARKER_START,
        "45 6 * * 1-5 old jarvis line",
        _MARKER_END,
    ]
    result = _replace_marker_block(existing, None)
    assert result == ["0 9 * * * some-other-job"]


def test_missing_crontab_binary_raises_clear_error(monkeypatch):
    def fake_run(*args, **kwargs):
        raise FileNotFoundError("crontab")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="No `crontab` command found"):
        schedule.cron_status()
