from datetime import datetime, timedelta

from jarvis import tasks as tasks_mod
from jarvis.models import Task


def _task(**overrides) -> Task:
    base = dict(
        task_id="1",
        title="HW3",
        course="ME 270",
        due_at=datetime.now().astimezone() + timedelta(days=2),
        notes="",
        priority="medium",
        completed=False,
        calendar_event_id=None,
        created_at=datetime.now().astimezone(),
    )
    base.update(overrides)
    return Task(**base)


def test_upcoming_tasks_excludes_far_future():
    near = _task(task_id="1", due_at=datetime.now().astimezone() + timedelta(days=2))
    far = _task(task_id="2", due_at=datetime.now().astimezone() + timedelta(days=30))
    result = tasks_mod.upcoming_tasks([near, far], within_days=7)
    assert [t.task_id for t in result] == ["1"]


def test_upcoming_tasks_always_includes_overdue_incomplete():
    overdue = _task(task_id="1", due_at=datetime.now().astimezone() - timedelta(days=5), completed=False)
    result = tasks_mod.upcoming_tasks([overdue], within_days=7)
    assert [t.task_id for t in result] == ["1"]


def test_upcoming_tasks_excludes_completed_by_default():
    done = _task(task_id="1", completed=True)
    assert tasks_mod.upcoming_tasks([done], within_days=7) == []
    assert len(tasks_mod.upcoming_tasks([done], within_days=7, include_completed=True)) == 1


def test_upcoming_tasks_sorted_by_due_date():
    later = _task(task_id="1", due_at=datetime.now().astimezone() + timedelta(days=5))
    sooner = _task(task_id="2", due_at=datetime.now().astimezone() + timedelta(days=1))
    result = tasks_mod.upcoming_tasks([later, sooner], within_days=7)
    assert [t.task_id for t in result] == ["2", "1"]


def test_round_trip_via_save_and_load(tmp_path, monkeypatch):
    monkeypatch.setattr(tasks_mod, "TASKS_DIR", tmp_path)
    monkeypatch.setattr(tasks_mod, "TASKS_PATH", tmp_path / "tasks.json")

    assert tasks_mod.load_tasks() == []

    items = [_task(task_id="1"), _task(task_id="2", title="Lab report")]
    tasks_mod.save_tasks(items)

    loaded = tasks_mod.load_tasks()
    assert [t.task_id for t in loaded] == ["1", "2"]
    assert loaded[1].title == "Lab report"


def test_complete_task(tmp_path, monkeypatch):
    monkeypatch.setattr(tasks_mod, "TASKS_DIR", tmp_path)
    monkeypatch.setattr(tasks_mod, "TASKS_PATH", tmp_path / "tasks.json")

    tasks_mod.save_tasks([_task(task_id="1")])

    assert tasks_mod.complete_task("1") is True
    assert tasks_mod.load_tasks()[0].completed is True
    assert tasks_mod.complete_task("missing") is False


def test_remove_task_without_calendar_sync(tmp_path, monkeypatch):
    monkeypatch.setattr(tasks_mod, "TASKS_DIR", tmp_path)
    monkeypatch.setattr(tasks_mod, "TASKS_PATH", tmp_path / "tasks.json")

    tasks_mod.save_tasks([_task(task_id="1", calendar_event_id=None), _task(task_id="2")])

    assert tasks_mod.remove_task("1") is True
    assert [t.task_id for t in tasks_mod.load_tasks()] == ["2"]
    assert tasks_mod.remove_task("does-not-exist") is False


def test_add_task_without_secrets_skips_calendar_sync(tmp_path, monkeypatch):
    monkeypatch.setattr(tasks_mod, "TASKS_DIR", tmp_path)
    monkeypatch.setattr(tasks_mod, "TASKS_PATH", tmp_path / "tasks.json")

    task = tasks_mod.add_task(
        "HW4", datetime.now().astimezone() + timedelta(days=3), secrets=None
    )
    assert task.calendar_event_id is None
    assert tasks_mod.load_tasks()[0].title == "HW4"
