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


def test_tag_l_shortcut_updates_learning(cli, add_session, tags):
    add_session("learning", date.today(), emoji="🍄")
    assert cli.run(["tag", "l", "🌼"]) == 0
    assert tags() == {"learning": "🌼"}


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
