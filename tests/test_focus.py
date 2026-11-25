"""Focus check after the ding, and q/Esc to stop a session."""

import pytest
from test_timer import START, FakeClock

import bonsai

# --- ask_focus: one keypress, no Enter -------------------------------------

def _keys(monkeypatch, *keys):
    it = iter(keys)
    monkeypatch.setattr(bonsai, "read_key", lambda: next(it))


@pytest.mark.parametrize("keys, expected", [
    (("y",), True), (("Y",), True), (("\r",), True), (("\n",), True),
    (("n",), False), (("N",), False),
    (("x", "q", "n"), False),  # other keys are ignored until y/n/Enter
    (("",), True),             # EOF counts as good
])
def test_ask_focus_single_key(monkeypatch, capsys, keys, expected):
    _keys(monkeypatch, *keys)
    assert bonsai.ask_focus() is expected
    out = capsys.readouterr().out
    assert "Good focus session? [Y/n]" in out
    assert out.rstrip().endswith("y" if expected else "n")


def test_ask_focus_ctrl_c_counts_as_good(monkeypatch, capsys):
    def boom():
        raise KeyboardInterrupt
    monkeypatch.setattr(bonsai, "read_key", boom)
    assert bonsai.ask_focus() is True


# --- start + focus check -----------------------------------------------------

def test_focused_session_keeps_plant(cli, rows):
    assert cli.run(["start", "work", "30"]) == 0
    (row,) = rows()
    assert row["completed"] == 1
    assert cli.events == ["caffeinate", "timer", "ding", "focus"]  # ding starts, then the question


def test_not_focused_session_keeps_hours_drops_plant(cli, rows, capsys):
    cli.focused = False
    assert cli.run(["start", "work", "30"]) == 0
    (row,) = rows()
    assert row["completed"] == 0
    assert row["actual_min"] == row["planned_min"] == 30
    assert row["source"] == "timer"
    assert cli.ding_calls == [("work", 30)]
    assert "planted" not in capsys.readouterr().out.replace("Nothing planted", "")


def test_stopped_early_skips_focus_check(cli, rows):
    cli.completed = False
    cli.elapsed_s = 10 * 60
    assert cli.run(["start", "work", "30"]) == 0
    assert "focus" not in cli.events
    assert rows()[0]["completed"] == 0


def test_row_saved_before_focus_question(cli, rows, monkeypatch):
    seen = []
    monkeypatch.setattr(bonsai, "ask_focus", lambda: seen.append(len(rows())) or True)
    cli.run(["start", "work", "30"])
    assert seen == [1]


# --- q / Esc to stop ---------------------------------------------------------

def test_run_timer_stops_on_key(monkeypatch, capsys):
    presses = iter([False, False, True])
    monkeypatch.setattr(bonsai, "stop_key_pressed", lambda: next(presses))
    clock = FakeClock(step=1)
    start_ts, end_ts, completed = bonsai.run_timer(25, "work", "🌵", clock=clock, sleep=lambda s: None)
    assert start_ts == START
    assert completed is False
    assert end_ts < START + 25 * 60


def test_stop_key_pressed_false_without_tty(monkeypatch):
    # pytest's stdin is not a terminal; must not block or raise.
    assert bonsai.stop_key_pressed() is False


@pytest.mark.parametrize("key, expected", [("q", True), ("Q", True), ("\x1b", True), ("x", False)])
def test_is_stop_key(key, expected):
    assert bonsai.is_stop_key(key) is expected


# --- ding in the background, stoppable ---------------------------------------

def test_ding_stops_before_next_play_when_answered(monkeypatch):
    import subprocess
    import threading
    stop = threading.Event()
    plays = []

    def fake_run(args, *a, **kw):
        plays.append(args[0])
        stop.set()  # the user answers during the first play
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(bonsai.time, "sleep", lambda s: None)
    bonsai.ding("work", 30, stop)
    assert plays == ["afplay"]  # no more dings, no notification


def test_start_ding_runs_in_background(monkeypatch):
    import threading
    started = threading.Event()
    release = threading.Event()

    def slow_ding(tag, minutes, stop=None):
        started.set()
        release.wait(2)

    monkeypatch.setattr(bonsai, "ding", slow_ding)
    stop = bonsai.start_ding("work", 30)
    assert started.wait(2)       # ding is running...
    assert not release.is_set()  # ...and start_ding already returned
    assert hasattr(stop, "set")
    release.set()
