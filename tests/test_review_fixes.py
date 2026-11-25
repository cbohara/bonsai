"""Regression tests for review round 1 fixes."""

import subprocess
import time
from datetime import date

import bonsai


def test_tag_w_shortcut_is_refused(cli, add_session, tags, capsys):
    add_session("learning", date.today(), emoji="🍄")
    code = cli.run(["tag", "w", "🍄"])
    out, err = capsys.readouterr()
    assert code != 0
    assert (out + err).strip()
    assert tags() == {"learning": "🍄"}


def test_learning_is_an_ordinary_life_tag(cli, tags):
    # No `l` shortcut and no built-in learning: first use asks like any new tag.
    cli.run(["start", "learning", "25"])
    assert [p.strip() for p in cli.prompts] == ['New tag "learning"? [y/N]']
    assert cli.timer_calls == [(25, "learning")]
    cli.run(["start", "l", "25"])
    assert [p.strip() for p in cli.prompts][-1] == 'New tag "l"? [y/N]'


def test_ding_escapes_quotes_in_notification(monkeypatch):
    calls = []

    def fake_run(args, *a, **kw):
        calls.append(list(args))
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(time, "sleep", lambda s: None)
    bonsai.ding('say "hi"\\', 25)
    osa = [c for c in calls if c[0] == "osascript"]
    assert osa == [["osascript", "-e",
                    'display notification "Say \\"hi\\"\\\\ session done — 25 min" with title "bonsai"']]
