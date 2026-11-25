"""DB layer on a temp DB: criteria 8-10."""

import sqlite3
from datetime import date
from pathlib import Path

import pytest

import bonsai

ALL8 = ["🍄", "🌻", "🌷", "🌼", "🌸", "🍀", "🌺", "🪻"]


def _columns(conn, table):
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]


# --- 8 -------------------------------------------------------------------
def test_init_db_and_path(tmp_path):
    path = tmp_path / "missing" / "nested" / "bonsai.db"
    conn = bonsai.init_db(path)
    assert isinstance(conn, sqlite3.Connection)
    assert path.exists()
    assert _columns(conn, "sessions") == [
        "id", "tag", "start", "end", "planned_min", "actual_min", "completed", "source"]
    assert _columns(conn, "tags") == ["name", "emoji"]
    assert _columns(conn, "settings") == ["key", "value"]

    conn.execute("INSERT INTO tags (name, emoji) VALUES ('writing', '🌻')")
    conn.commit()
    conn.close()

    conn2 = bonsai.init_db(path)  # second call: no error, data kept
    assert dict(conn2.execute("SELECT name, emoji FROM tags")) == {"writing": "🌻"}
    conn2.close()


def test_init_db_and_path_env(tmp_path, monkeypatch):
    monkeypatch.setenv("BONSAI_DB", str(tmp_path / "x" / "custom.db"))
    assert Path(bonsai.db_path()) == tmp_path / "x" / "custom.db"


def test_init_db_and_path_default_home(tmp_path, monkeypatch):
    monkeypatch.delenv("BONSAI_DB", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert Path(bonsai.db_path()) == tmp_path / ".bonsai" / "bonsai.db"


# --- 9 -------------------------------------------------------------------
@pytest.mark.parametrize(
    "used, expected",
    [([], "🍄"), (["🍄", "🌻"], "🌷"), (["🌻", "🍄"], "🌷"), (["🌻"], "🍄"),
     (["🍄", "🌻", "🌷", "🌼", "🌸", "🍀", "🌺"], "🪻"),
     (ALL8, "🍄"), (ALL8 + ["🍄"], "🌻"), (ALL8 + ["🍄", "🌻"], "🌷")],
)
def test_default_emoji_assignment(used, expected):
    assert bonsai.next_default_emoji(used) == expected


def test_default_emoji_assignment_ensure_tag(tmp_path):
    conn = bonsai.init_db(tmp_path / "t.db")
    conn.execute("INSERT INTO tags (name, emoji) VALUES ('learning', '🍄')")
    conn.commit()

    bonsai.ensure_tag(conn, "writing")
    bonsai.ensure_tag(conn, "reading")
    bonsai.ensure_tag(conn, "writing")  # existing: unchanged
    bonsai.ensure_tag(conn, "work")     # never stored
    assert dict(conn.execute("SELECT name, emoji FROM tags")) == {
        "learning": "🍄", "writing": "🌻", "reading": "🌷"}


def test_default_emoji_assignment_ensure_tag_keeps_custom(tmp_path):
    conn = bonsai.init_db(tmp_path / "t.db")
    conn.execute("INSERT INTO tags (name, emoji) VALUES ('writing', '🌺')")
    conn.commit()
    bonsai.ensure_tag(conn, "writing")
    assert dict(conn.execute("SELECT name, emoji FROM tags")) == {"writing": "🌺"}


# --- 10 ------------------------------------------------------------------
@pytest.mark.parametrize("name, emoji", [("writing", "🌵"), ("work", "🍄"), ("work", "🌵")])
def test_cactus_and_work_refused_validate(name, emoji):
    with pytest.raises(ValueError):
        bonsai.validate_tag_emoji(name, emoji)


def test_cactus_and_work_refused_validate_allows_normal():
    assert bonsai.validate_tag_emoji("writing", "🌻") is None


def test_cactus_and_work_refused_set_tag_emoji(tmp_path):
    conn = bonsai.init_db(tmp_path / "t.db")
    conn.execute("INSERT INTO tags (name, emoji) VALUES ('writing', '🍄')")
    conn.commit()

    with pytest.raises(ValueError):
        bonsai.set_tag_emoji(conn, "writing", "🌵")
    with pytest.raises(ValueError):
        bonsai.set_tag_emoji(conn, "work", "🍄")
    assert dict(conn.execute("SELECT name, emoji FROM tags")) == {"writing": "🍄"}

    bonsai.set_tag_emoji(conn, "writing", "🌷")  # a valid change goes through
    assert dict(conn.execute("SELECT name, emoji FROM tags")) == {"writing": "🌷"}


@pytest.mark.parametrize("argv", [["tag", "writing", "🌵"], ["tag", "work", "🍄"]])
def test_cactus_and_work_refused_cli(argv, cli, add_session, tags, capsys):
    add_session("writing", date.today(), emoji="🌻")
    code = cli.run(argv)
    out, err = capsys.readouterr()
    assert code != 0
    assert (out + err).strip()
    assert tags() == {"writing": "🌻"}
