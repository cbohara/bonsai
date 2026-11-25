"""run_timer contract with a fake clock and sleep: criterion 14."""

import sys

import bonsai

START = 1_800_000_000.0


class FakeClock:
    """Returns START first, then each value from `after` (last one repeats)."""

    def __init__(self, *after, step=None):
        self.calls = 0
        self.after = after
        self.step = step

    def __call__(self):
        self.calls += 1
        if self.calls > 10_000:
            raise AssertionError("run_timer never reached its deadline")
        if self.calls == 1:
            return START
        if self.step is not None:
            return START + self.step * (self.calls - 1)
        return self.after[min(self.calls - 2, len(self.after) - 1)]


def _interrupt(_seconds):
    raise KeyboardInterrupt


def test_run_timer_contract_completed(capsys):
    deadline = START + 2 * 60
    clock = FakeClock(deadline + 5)
    start_ts, end_ts, completed = bonsai.run_timer(2, "work", "🌵", clock=clock, sleep=lambda s: None)
    assert (start_ts, completed) == (START, True)
    assert end_ts >= deadline


def test_run_timer_contract_polls_until_deadline(capsys):
    # Clock advances 7 s per read; the timer must keep polling, not stop early.
    deadline = START + 1 * 60
    start_ts, end_ts, completed = bonsai.run_timer(
        1, "learning", "🍄", clock=FakeClock(step=7), sleep=lambda s: None)
    assert start_ts == START
    assert completed is True
    assert deadline <= end_ts < deadline + 7 * 3


def test_run_timer_contract_stopped(capsys):
    clock = FakeClock(START + 30)
    start_ts, end_ts, completed = bonsai.run_timer(25, "work", "🌵", clock=clock, sleep=_interrupt)
    assert (start_ts, end_ts, completed) == (START, START + 30, False)
    assert end_ts < START + 25 * 60


def test_run_timer_contract_no_tty(capsys):
    # capsys replaces stdout with a non-TTY; the timer must still work.
    assert not sys.stdout.isatty()
    start_ts, end_ts, completed = bonsai.run_timer(
        1, "work", "🌵", clock=FakeClock(START + 61), sleep=lambda s: None)
    assert (start_ts, completed) == (START, True)
    assert end_ts >= START + 60
