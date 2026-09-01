"""Installs `jarvis brief` as a recurring OS-level job so it actually runs every
weekday morning without you remembering to - cron on Linux/macOS, Task Scheduler
on Windows."""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

from jarvis.config import REPO_ROOT

_MARKER_START = "# >>> jarvis-morning-brief >>>"
_MARKER_END = "# <<< jarvis-morning-brief <<<"
_TASK_NAME = "JarvisMorningBrief"

DEFAULT_OUTPUT_DIR = REPO_ROOT / "briefings"


def build_cron_line(time_str: str, days: str, output_dir: Path) -> str:
    hour, minute = time_str.split(":")
    log_path = output_dir / "cron.log"
    command = (
        f"cd {REPO_ROOT} && {sys.executable} -m jarvis.cli brief "
        f"--output {output_dir}/$(date +\\%F).md >> {log_path} 2>&1"
    )
    return f"{int(minute)} {int(hour)} * * {days} {command}"


def _replace_marker_block(existing_lines: list[str], new_line: str | None) -> list[str]:
    """Drops any previously-installed jarvis block and (if given) appends a fresh
    one - keeps re-running `install` idempotent instead of piling up duplicates."""
    kept: list[str] = []
    skipping = False
    for line in existing_lines:
        stripped = line.strip()
        if stripped == _MARKER_START:
            skipping = True
            continue
        if stripped == _MARKER_END:
            skipping = False
            continue
        if not skipping:
            kept.append(line)

    if new_line is not None:
        kept += [_MARKER_START, new_line, _MARKER_END]
    return kept


_CRON_MISSING_MSG = (
    "No `crontab` command found on this system. Auto-scheduling needs cron "
    "(standard on Linux/macOS) - install it, or set up the recurring run some "
    "other way (see the README's manual cron example)."
)


def _run_crontab(args: list[str], input_text: str | None = None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["crontab", *args], input=input_text, text=True, capture_output=True)
    except FileNotFoundError as exc:
        raise RuntimeError(_CRON_MISSING_MSG) from exc


def _read_crontab() -> list[str]:
    result = _run_crontab(["-l"])
    return result.stdout.splitlines() if result.returncode == 0 else []


def _write_crontab(lines: list[str]) -> None:
    content = "\n".join(lines) + ("\n" if lines else "")
    result = _run_crontab(["-"], input_text=content)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to update crontab: {result.stderr.strip()}")


def install_cron(time_str: str, days: str, output_dir: Path) -> str:
    output_dir.mkdir(parents=True, exist_ok=True)
    line = build_cron_line(time_str, days, output_dir)
    _write_crontab(_replace_marker_block(_read_crontab(), line))
    return line


def uninstall_cron() -> bool:
    current = _read_crontab()
    if _MARKER_START not in current:
        return False
    _write_crontab(_replace_marker_block(current, None))
    return True


def cron_status() -> str | None:
    lines = _read_crontab()
    if _MARKER_START not in lines:
        return None
    idx = lines.index(_MARKER_START)
    return lines[idx + 1] if idx + 1 < len(lines) else None


def install_windows_task(time_str: str, output_dir: Path) -> str:
    output_dir.mkdir(parents=True, exist_ok=True)
    command = f'"{sys.executable}" -m jarvis.cli brief --output "{output_dir}\\brief.md"'
    result = subprocess.run(
        [
            "schtasks", "/Create", "/SC", "WEEKLY", "/D", "MON,TUE,WED,THU,FRI",
            "/TN", _TASK_NAME, "/TR", command, "/ST", time_str, "/F",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to create scheduled task: {result.stderr.strip()}")
    return command


def uninstall_windows_task() -> bool:
    result = subprocess.run(["schtasks", "/Delete", "/TN", _TASK_NAME, "/F"], capture_output=True, text=True)
    return result.returncode == 0


def windows_task_status() -> str | None:
    result = subprocess.run(["schtasks", "/Query", "/TN", _TASK_NAME], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def install(time_str: str = "06:45", days: str = "1-5", output_dir: Path | None = None) -> str:
    output_dir = output_dir or DEFAULT_OUTPUT_DIR
    if platform.system() == "Windows":
        return install_windows_task(time_str, output_dir)
    return install_cron(time_str, days, output_dir)


def uninstall() -> bool:
    if platform.system() == "Windows":
        return uninstall_windows_task()
    return uninstall_cron()


def status() -> str | None:
    if platform.system() == "Windows":
        return windows_task_status()
    return cron_status()
