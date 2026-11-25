# /// script
# requires-python = ">=3.12"
# dependencies = ["rich"]
# ///
"""bonsai: terminal Pomodoro + time tracker with a garden. (STUB: red phase only.)"""

import sqlite3
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

SOUND_FILE = "/System/Library/Sounds/Glass.aiff"
DING_REPEATS = 3
DING_GAP_S = 1.5
VOLUME = 1.0
DEFAULT_MINUTES = 30
WORK_CAP_H = 40
DEFAULT_EMOJIS = ["🍄", "🌻", "🌷", "🌼", "🌸", "🍀", "🌺", "🪻"]


def plants_for_session(actual_min: float, completed: bool) -> int:
    raise NotImplementedError


def plant_stage(progress: float, emoji: str, stopped: bool = False) -> str:
    raise NotImplementedError


def week_bounds(d: date) -> tuple[date, date]:
    raise NotImplementedError


def session_date(start_iso: str) -> date:
    raise NotImplementedError


def current_streak(completed_dates: set[date], today: date) -> int:
    raise NotImplementedError


def best_streak(completed_dates: set[date]) -> int:
    raise NotImplementedError


def next_default_emoji(used: list[str]) -> str:
    raise NotImplementedError


def validate_tag_emoji(name: str, emoji: str) -> None:
    raise NotImplementedError


def garden_row(plants: list[tuple[str, int]], emojis: dict[str, str]) -> str:
    raise NotImplementedError


def bar_color(work_hours: float) -> str:
    raise NotImplementedError


def cap_warning(work_hours: float) -> str | None:
    raise NotImplementedError


def actual_minutes(start_ts: float, end_ts: float, planned_min: int) -> float:
    raise NotImplementedError


def resolve_tag(tag: str) -> str:
    raise NotImplementedError


def db_path() -> Path:
    raise NotImplementedError


def init_db(path: Path) -> sqlite3.Connection:
    raise NotImplementedError


def ensure_tag(conn, name: str) -> None:
    raise NotImplementedError


def set_tag_emoji(conn, name: str, emoji: str) -> None:
    raise NotImplementedError


def run_timer(planned_min: int, tag: str, emoji: str,
              clock=time.time, sleep=time.sleep) -> tuple[float, float, bool]:
    raise NotImplementedError


def ding(tag: str, minutes: int) -> None:
    raise NotImplementedError


def start_caffeinate(pid: int) -> subprocess.Popen:
    raise NotImplementedError


def confirm(prompt: str) -> bool:
    raise NotImplementedError


def main(argv: list[str] | None = None) -> int:
    raise NotImplementedError


if __name__ == "__main__":
    sys.exit(main())
