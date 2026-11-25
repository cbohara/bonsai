"""ding, caffeinate, import hygiene (all monkeypatched): criteria 25-27."""

import importlib
import subprocess
import time
from pathlib import Path

import pytest

import bonsai


class Recorder:
    """Fake subprocess.run / time.sleep that log into one ordered event list."""

    def __init__(self, afplay_error=None, afplay_rc=0):
        self.events = []
        self.afplay_error = afplay_error
        self.afplay_rc = afplay_rc

    def run(self, args, *a, **kw):
        args = list(args)
        self.events.append(("run", args))
        rc = 0
        if args and args[0] == "afplay":
            if self.afplay_error:
                raise self.afplay_error
            rc = self.afplay_rc
        if rc and kw.get("check"):
            raise subprocess.CalledProcessError(rc, args)
        return subprocess.CompletedProcess(args, rc)

    def sleep(self, s):
        self.events.append(("sleep", s))

    def calls(self, prog):
        return [args for kind, args in self.events if kind == "run" and args[0] == prog]


@pytest.fixture
def rec(monkeypatch):
    r = Recorder()
    monkeypatch.setattr(subprocess, "run", r.run)
    monkeypatch.setattr(time, "sleep", r.sleep)
    return r


def _notification(text):
    return ["osascript", "-e", f'display notification "{text}" with title "bonsai"']


# --- 25 ------------------------------------------------------------------
def test_ding_sequence_and_fallback(rec, capfd):
    bonsai.ding("work", 30)

    shape = [("run", args[0]) if kind == "run" else (kind, args) for kind, args in rec.events]
    assert shape == [
        ("run", "afplay"), ("sleep", bonsai.DING_GAP_S),
        ("run", "afplay"), ("sleep", bonsai.DING_GAP_S),
        ("run", "afplay"), ("run", "osascript"),
    ]
    for args in rec.calls("afplay"):
        assert args[:2] == ["afplay", "-v"]
        assert float(args[2]) == bonsai.VOLUME
        assert args[3:] == [bonsai.SOUND_FILE]
    assert rec.calls("osascript") == [_notification("Work session done — 30 min")]
    out, err = capfd.readouterr()
    assert "\a" in out + err


def test_ding_sequence_and_fallback_capitalizes_life_tag(rec):
    bonsai.ding("learning", 45)
    assert rec.calls("osascript") == [_notification("Learning session done — 45 min")]
    assert "sound name" not in rec.calls("osascript")[0][2]


@pytest.mark.parametrize(
    "error, rc", [(FileNotFoundError("afplay"), 0), (None, 1)], ids=["afplay-missing", "afplay-nonzero"]
)
def test_ding_sequence_and_fallback_afplay_fails(monkeypatch, capfd, error, rc):
    r = Recorder(afplay_error=error, afplay_rc=rc)
    monkeypatch.setattr(subprocess, "run", r.run)
    monkeypatch.setattr(time, "sleep", r.sleep)

    bonsai.ding("work", 25)  # must not raise

    assert r.calls("osascript") == [_notification("Work session done — 25 min")]
    out, err = capfd.readouterr()
    assert "\a" in out + err
    assert (out + err).replace("\a", "").strip(), "expected a printed warning"


def test_ding_sequence_and_fallback_success_prints_no_warning(rec, capfd):
    bonsai.ding("work", 30)
    out, err = capfd.readouterr()
    assert rec.calls("osascript")
    assert (out + err).replace("\a", "").strip() == ""


# --- 26 ------------------------------------------------------------------
def test_caffeinate_argv(monkeypatch):
    launched = []

    class FakePopen:
        def __init__(self, args, *a, **kw):
            launched.append([str(x) for x in args])

    monkeypatch.setattr(subprocess, "Popen", FakePopen)
    proc = bonsai.start_caffeinate(4242)
    assert launched == [["caffeinate", "-i", "-w", "4242"]]
    assert isinstance(proc, FakePopen)


# --- 27 ------------------------------------------------------------------
def test_import_is_inert(tmp_path, monkeypatch):
    home = tmp_path / "inert-home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("BONSAI_DB", raising=False)
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: calls.append(("run", a)))
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: calls.append(("Popen", a)))

    importlib.reload(bonsai)

    assert list(home.iterdir()) == []
    assert calls == []
    # The DB location is resolved lazily (at call time, from HOME), not at import.
    assert Path(bonsai.db_path()) == home / ".bonsai" / "bonsai.db"
    assert list(home.iterdir()) == []
