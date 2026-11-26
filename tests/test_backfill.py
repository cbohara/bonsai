"""backfill.py: one-time Toggl import, docs/BACKFILL.md."""

import csv
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest

import backfill
import bonsai

TODAY = date.today()
D1 = TODAY - timedelta(days=3)
D2 = TODAY - timedelta(days=2)
COLS = ["date", "start", "end", "duration_seconds", "duration_minutes", "description", "project", "tags"]


def row(day, hhmm, minutes, project="Working", description="work"):
    start = f"{day.isoformat()}T{hhmm}:00"
    h, m = map(int, hhmm.split(":"))
    end_min = h * 60 + m + minutes
    end = f"{day.isoformat()}T{int(end_min // 60):02d}:{int(end_min % 60):02d}:00"
    return {"date": day.isoformat(), "start": start, "end": end,
            "duration_seconds": int(minutes * 60), "duration_minutes": minutes,
            "description": description, "project": project, "tags": ""}


def set_aside_files(path):
    return sorted(Path(path).parent.glob("toggl-set-aside-*.csv"))


@pytest.fixture
def csvfile(tmp_path):
    def _write(rows):
        path = tmp_path / "toggl.csv"
        with path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLS)
            w.writeheader()
            w.writerows(rows)
        return str(path)
    return _write


SAMPLE = [
    row(D1, "09:00", 60),
    row(D1, "11:00", 30.4, project="Learning", description="deep learning ai"),
    row(D2, "08:00", 45, project="Tinkering", description="bonsai"),
    row(D2, "10:00", 0),
    row(D2, "12:00", 90, project="", description="work"),
    row(D2, "15:00", 20, project="", description="learning"),
]


@pytest.mark.parametrize("project, expected", [
    ("Working", "work"), ("Learning", "study"), ("Tinkering", "tinker"),
    ("", None), ("Side gig", None), ("working", None),
])
def test_toggl_tag(project, expected):
    assert backfill.toggl_tag(project) == expected


def test_dry_run_reports_and_saves_nothing(cli, rows, csvfile, capsys):
    path = csvfile(SAMPLE)
    assert backfill.main(["import", path, "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "6 rows" in out
    assert "1 zero-length" in out
    assert "2 set aside" in out
    assert "3 sessions" in out
    assert f"{D1.isoformat()} to {D2.isoformat()}" in out
    assert "work 1.0" in out and "study 0.5" in out and "tinker 0.8" in out
    assert "nothing saved" in out.lower()
    assert rows() == []
    assert set_aside_files(path) == []


def test_import_saves_sessions(cli, rows, tags, csvfile):
    assert backfill.main(["import", csvfile(SAMPLE)]) == 0
    saved = rows()
    assert [r["tag"] for r in saved] == ["work", "study", "tinker"]
    first = saved[0]
    assert first["start"].startswith(f"{D1.isoformat()}T09:00:00")
    assert first["end"].startswith(f"{D1.isoformat()}T10:00:00")
    assert first["start"][19] in "+-"  # stored with offset, like other sessions
    assert saved[1]["planned_min"] == 30 and saved[1]["actual_min"] == pytest.approx(30.0)
    assert all(r["completed"] == 1 and r["source"] == "toggl" for r in saved)
    assert tags() == {"study": bonsai.DEFAULT_EMOJIS[0], "tinker": bonsai.DEFAULT_EMOJIS[1]}
    assert cli.prompts == []


def test_import_twice_adds_nothing(cli, rows, csvfile, capsys):
    path = csvfile(SAMPLE)
    backfill.main(["import", path])
    capsys.readouterr()
    assert backfill.main(["import", path]) == 0
    assert len(rows()) == 3
    assert "3 already imported" in capsys.readouterr().out


def test_existing_bonsai_session_same_start_is_skipped(cli, rows, csvfile, add_session):
    add_session("work", D1, "09:00", actual_min=120, source="manual")
    assert backfill.main(["import", csvfile(SAMPLE)]) == 0
    saved = rows()
    assert len(saved) == 3  # 1 existing + 2 new
    assert sum(1 for r in saved if r["start"].startswith(f"{D1.isoformat()}T09:00")) == 1


def test_unknown_project_skipped_rest_imported(cli, rows, csvfile, capsys):
    path = csvfile(SAMPLE + [row(D2, "18:00", 30, project="Side gig"),
                             row(D2, "19:00", 30, project="Side gig")])
    assert backfill.main(["import", path]) == 0
    out = capsys.readouterr().out
    assert "Side gig (2)" in out
    assert "4 set aside" in out
    assert len(rows()) == 3
    assert all(r["tag"] != "side gig" for r in rows())


def test_unknown_project_fixed_then_rerun_adds_only_those(cli, rows, csvfile):
    bad = row(D2, "18:00", 30, project="Side gig")
    backfill.main(["import", csvfile(SAMPLE + [bad])])
    backfill.main(["import", csvfile(SAMPLE + [{**bad, "project": "Tinkering"}])])
    assert len(rows()) == 4


def test_set_aside_rows_written_to_csv(cli, csvfile, capsys):
    path = csvfile(SAMPLE + [row(D2, "18:00", 30, project="Side gig")])
    backfill.main(["import", path])
    (aside,) = set_aside_files(path)
    assert str(aside) in capsys.readouterr().out
    with aside.open(newline="") as f:
        got = list(csv.DictReader(f))
    assert list(got[0]) == COLS
    assert [(r["start"][11:16], r["project"], r["description"]) for r in got] == [
        ("12:00", "", "work"), ("15:00", "", "learning"), ("18:00", "Side gig", "work")]


def test_set_aside_rows_import_once_given_a_project(cli, rows, csvfile):
    path = csvfile(SAMPLE)
    backfill.main(["import", path])
    (aside,) = set_aside_files(path)
    text = aside.read_text().replace(",,", ",Working,", 1)  # fix the first row's project
    aside.write_text(text)
    backfill.main(["import", str(aside)])
    assert len(rows()) == 4


def test_imported_days_show_in_garden(cli, csvfile, day_row, capsys):
    backfill.main(["import", csvfile(SAMPLE)])
    capsys.readouterr()
    cli.run(["garden"])
    line = day_row(capsys.readouterr().out, D1, plants_only=True)
    assert line is not None and "🌵" in line


def test_rerun_keeps_edited_set_aside_file(cli, csvfile):
    path = csvfile(SAMPLE)
    backfill.main(["import", path])
    (aside,) = set_aside_files(path)
    aside.write_text(aside.read_text().replace(",,", ",Working,"))
    edited = aside.read_text()
    backfill.main(["import", path])
    assert aside.read_text() == edited
    assert len(set_aside_files(path)) == 2


def test_duplicate_check_ignores_timezone_offset(cli, rows, csvfile, dbfile, capsys):
    """Same clock time saved under another offset (e.g. imported while travelling) still matches."""
    path = csvfile(SAMPLE)
    backfill.main(["import", path])
    conn = sqlite3.connect(dbfile)
    conn.execute("UPDATE sessions SET start = substr(start, 1, 19) || '+09:00'")
    conn.commit()
    conn.close()
    capsys.readouterr()
    backfill.main(["import", path])
    assert len(rows()) == 3
    assert "3 already imported" in capsys.readouterr().out
