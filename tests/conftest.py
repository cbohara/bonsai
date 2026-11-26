"""Shared test isolation and small helpers for bonsai tests.

Every test gets a temp BONSAI_DB and HOME, and real subprocesses are blocked,
so nothing can play a sound, show a notification, run caffeinate, or touch
the real ~/.bonsai.
"""

import re
import sqlite3
import subprocess
import threading
from datetime import date, datetime, timedelta
from datetime import time as dtime

import pytest

import bonsai

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY, tag TEXT NOT NULL, start TEXT NOT NULL, end TEXT NOT NULL,
  planned_min INTEGER NOT NULL, actual_min REAL NOT NULL, completed INTEGER NOT NULL,
  source TEXT NOT NULL DEFAULT 'timer');
CREATE TABLE IF NOT EXISTS tags (name TEXT PRIMARY KEY, emoji TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
"""


def _blocked(*args, **kwargs):
    raise AssertionError(f"real subprocess attempted in a test: {args!r}")


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("BONSAI_DB", str(tmp_path / "data" / "bonsai.db"))
    monkeypatch.setenv("COLUMNS", "200")
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    monkeypatch.setattr(subprocess, "run", _blocked)
    monkeypatch.setattr(subprocess, "Popen", _blocked)
    return tmp_path


@pytest.fixture
def dbfile(isolated):
    return isolated / "data" / "bonsai.db"


@pytest.fixture
def rows(dbfile):
    """Return all session rows (dicts, ordered by id); [] if no DB yet."""

    def _rows():
        if not dbfile.exists():
            return []
        conn = sqlite3.connect(dbfile)
        conn.row_factory = sqlite3.Row
        try:
            names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "sessions" not in names:
                return []
            return [dict(r) for r in conn.execute("SELECT * FROM sessions ORDER BY id")]
        finally:
            conn.close()

    return _rows


@pytest.fixture
def tags(dbfile):
    """Return the tags table as {name: emoji}; {} if no DB yet."""

    def _tags():
        if not dbfile.exists():
            return {}
        conn = sqlite3.connect(dbfile)
        try:
            names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if "tags" not in names:
                return {}
            return dict(conn.execute("SELECT name, emoji FROM tags"))
        finally:
            conn.close()

    return _tags


@pytest.fixture
def add_session(dbfile):
    """Insert a session row directly (schema from the human spec)."""

    def _add(tag, day, hhmm="09:00", actual_min=30.0, completed=1, planned_min=None,
             source="timer", emoji=None):
        dbfile.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(dbfile)
        conn.executescript(SCHEMA)
        h, m = map(int, hhmm.split(":"))
        start = datetime.combine(day, dtime(h, m)).astimezone()
        end = start + timedelta(minutes=actual_min)
        conn.execute(
            "INSERT INTO sessions (tag, start, end, planned_min, actual_min, completed, source)"
            " VALUES (?,?,?,?,?,?,?)",
            (tag, start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds"),
             int(planned_min if planned_min is not None else max(1, round(actual_min))),
             float(actual_min), completed, source),
        )
        if tag != "work" and emoji:
            conn.execute("INSERT OR IGNORE INTO tags (name, emoji) VALUES (?,?)", (tag, emoji))
        conn.commit()
        conn.close()

    return _add


class Cli:
    """Stubs for main()'s side-effect seams, plus a runner."""

    def __init__(self, monkeypatch):
        self.events = []
        self.timer_calls = []  # (planned_min, tag)
        self.ding_calls = []
        self.caffeinate_pids = []
        self.prompts = []
        self.answer = True
        self.on_confirm = None
        self.elapsed_s = None  # default: exactly planned_min * 60
        self.completed = True
        self.focused = True
        monkeypatch.setattr(bonsai, "run_timer", self._run_timer)
        monkeypatch.setattr(bonsai, "ask_focus", self._ask_focus)
        monkeypatch.setattr(bonsai, "ding", self._ding)
        monkeypatch.setattr(bonsai, "start_ding", self._start_ding)
        monkeypatch.setattr(bonsai, "start_caffeinate", self._caffeinate)
        monkeypatch.setattr(bonsai, "confirm", self._confirm)

    def _run_timer(self, planned_min, tag, emoji, clock=None, sleep=None):
        self.events.append("timer")
        self.timer_calls.append((planned_min, tag))
        start = datetime.now().timestamp() - 1
        elapsed = self.elapsed_s if self.elapsed_s is not None else planned_min * 60
        self.last_timer = (start, start + elapsed, self.completed)
        return self.last_timer

    def _ding(self, tag, minutes):
        self.events.append("ding")
        self.ding_calls.append((tag, minutes))

    def _ask_focus(self):
        self.events.append("focus")
        return self.focused

    def _start_ding(self, tag, minutes):
        self._ding(tag, minutes)  # synchronous in tests
        return threading.Event()

    def _caffeinate(self, pid):
        self.events.append("caffeinate")
        self.caffeinate_pids.append(pid)

        class _Proc:
            def terminate(self): pass
            def kill(self): pass
            def wait(self, *a, **k): return 0
            def poll(self): return 0

        return _Proc()

    def _confirm(self, prompt):
        self.prompts.append(prompt)
        if self.on_confirm:
            self.on_confirm(prompt)
        return self.answer

    def run(self, argv):
        """Call main(argv); return its exit code (argparse SystemExit included)."""
        try:
            return bonsai.main(argv)
        except SystemExit as e:
            return e.code if isinstance(e.code, int) else (0 if e.code is None else 1)


@pytest.fixture
def cli(monkeypatch):
    return Cli(monkeypatch)


def _date_patterns(d: date):
    texts = {
        d.isoformat(), d.strftime("%m-%d"), d.strftime("%m/%d"),
        d.strftime("%b %d"), f"{d:%b} {d.day}", d.strftime("%d %b"), f"{d.day} {d:%b}",
        d.strftime("%a %d"), f"{d:%a} {d.day}",
    }
    return [re.compile(r"(?<!\d)" + re.escape(t) + r"(?!\d)") for t in texts]


@pytest.fixture
def day_row():
    """Find the output line for day d: it names the date (or, if weekday_ok,
    the weekday) and, unless plants_only (garden), carries an hours value like 0.0."""

    def _find(out, d, weekday_ok=False, plants_only=False):
        pats = _date_patterns(d)
        if weekday_ok:
            pats.append(re.compile(rf"\b({d:%a}|{d:%A})\b"))
        for line in out.splitlines():
            if (plants_only or re.search(r"\d+\.\d", line)) and "total" not in line.lower() and any(
                p.search(line) for p in pats
            ):
                return line
        return None

    return _find


@pytest.fixture
def freeze_today(monkeypatch):
    """Pin bonsai's date.today() to a given day."""

    def _freeze(day):
        class Fixed(date):
            @classmethod
            def today(cls):
                return day

        monkeypatch.setattr(bonsai, "date", Fixed)

    return _freeze
