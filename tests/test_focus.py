"""Focus check after the ding, and q/Esc to stop a session."""

import builtins

import pytest
from test_timer import START, FakeClock

import bonsai

# --- ask_focus ---------------------------------------------------------------

@pytest.mark.parametrize("typed, expected", [
    ("", True), ("y", True), ("Y", True), ("yes", True),
    ("n", False), ("N", False), ("no", False),
])
def test_ask_focus_answers(monkeypatch, typed, expected):
    monkeypatch.setattr(builtins, "input", lambda prompt="": typed)
    assert bonsai.ask_focus() is expected


@pytest.mark.parametrize("exc", [EOFError, KeyboardInterrupt])
def test_ask_focus_defaults_to_good_when_interrupted(monkeypatch, capsys, exc):
    def boom(prompt=""):
        raise exc
    monkeypatch.setattr(builtins, "input", boom)
    assert bonsai.ask_focus() is True


def test_ask_focus_prompt_text(monkeypatch):
    seen = []
    monkeypatch.setattr(builtins, "input", lambda prompt="": seen.append(prompt) or "")
    bonsai.ask_focus()
    assert "Good focus session? [Y/n]" in seen[0]


# --- start + focus check -----------------------------------------------------

def test_focused_session_keeps_plant(cli, rows):
    assert cli.run(["start", "work", "30"]) == 0
    (row,) = rows()
    assert row["completed"] == 1
    assert cli.events == ["caffeinate", "timer", "ding", "focus"]


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
