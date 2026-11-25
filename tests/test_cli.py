"""CLI via main(argv) on a temp DB, seams stubbed: criteria 11-13, 15-24."""

import csv
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

import bonsai

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)
MONDAY = TODAY - timedelta(days=TODAY.weekday())


def _week_args(d):
    """`week` args whose output contains day d (d is this week or last)."""
    return ["week"] if d >= MONDAY else ["week", "--last"]


def _totals_line(out):
    lines = [ln for ln in out.splitlines() if "total" in ln.lower() and re.search(r"\d+\.\d", ln)]
    assert lines, f"no totals row in:\n{out}"
    return lines


# --- 11 ------------------------------------------------------------------
def test_tag_command_set_is_retroactive(cli, rows, tags, day_row, capsys):
    assert cli.run(["log", "writing", "30", "--date", TODAY.isoformat(), "--at", "09:00"]) == 0
    assert tags()["writing"] == "🍄"  # first default

    assert cli.run(["tag", "writing", "🌻"]) == 0
    assert tags()["writing"] == "🌻"
    capsys.readouterr()

    cli.run(["today"])
    out = capsys.readouterr().out
    assert "🌻" in out and "🍄" not in out

    cli.run(["garden"])
    row = day_row(capsys.readouterr().out, TODAY)
    assert row is not None and "🌻" in row and "🍄" not in row


def test_tag_command_lists_all(cli, add_session, capsys):
    add_session("writing", TODAY, emoji="🌻")
    add_session("reading", TODAY, emoji="🌷")
    assert cli.run(["tag"]) == 0
    lines = capsys.readouterr().out.splitlines()

    def line_for(name):
        found = [ln for ln in lines if re.search(rf"\b{name}\b", ln)]
        assert len(found) == 1, f"{name}: {found}"
        return found[0]

    work = line_for("work")
    assert "🌵" in work and work.count("work") >= 2  # name and group
    for name, emoji in (("writing", "🌻"), ("reading", "🌷")):
        assert emoji in line_for(name) and "life" in line_for(name)


def test_tag_command_shows_one(cli, add_session, capsys):
    add_session("writing", TODAY, emoji="🌻")
    add_session("reading", TODAY, emoji="🌷")
    assert cli.run(["tag", "writing"]) == 0
    out = capsys.readouterr().out
    assert "🌻" in out and "life" in out
    assert "reading" not in out and "🌷" not in out and "🌵" not in out


def test_tag_command_creates_new_without_prompt(cli, tags):
    assert cli.run(["tag", "reading", "🌷"]) == 0
    assert cli.prompts == []
    assert tags() == {"reading": "🌷"}


# --- 12 ------------------------------------------------------------------
def test_remembered_defaults_empty_db(cli):
    cli.run([])
    cli.run(["start"])
    assert cli.timer_calls == [(30, "work"), (30, "work")]


def test_remembered_defaults_after_start(cli):
    cli.run(["start", "writing", "25"])
    cli.run([])
    cli.run(["start"])
    cli.run(["start", "w"])
    assert cli.timer_calls == [(25, "writing"), (25, "writing"), (25, "writing"), (25, "work")]


def test_remembered_defaults_log_does_not_update(cli):
    cli.run(["start", "writing", "25"])
    cli.run(["log", "learning", "45"])
    cli.run([])
    assert cli.timer_calls[-1] == (25, "writing")


# --- 13 ------------------------------------------------------------------
def test_start_writes_row_and_dings_completed(cli, rows, capsys):
    assert cli.run(["start", "work", "25"]) == 0
    (row,) = rows()
    start_ts, end_ts, _ = cli.last_timer
    assert {k: row[k] for k in ("tag", "planned_min", "completed", "source")} == {
        "tag": "work", "planned_min": 25, "completed": 1, "source": "timer"}
    assert row["actual_min"] == pytest.approx(25.0)
    assert datetime.fromisoformat(row["start"]).timestamp() == pytest.approx(start_ts, abs=1)
    assert datetime.fromisoformat(row["end"]).timestamp() == pytest.approx(end_ts, abs=1)
    assert cli.ding_calls == [("work", 25)]
    out = capsys.readouterr().out.strip()
    assert out and len(out.splitlines()) >= 1


def test_start_writes_row_and_dings_stopped(cli, rows):
    cli.completed = False
    cli.elapsed_s = 600  # 10 of 25 minutes
    cli.run(["start", "work", "25"])
    (row,) = rows()
    assert row["completed"] == 0
    assert row["actual_min"] == pytest.approx(10.0)
    assert row["planned_min"] == 25
    assert cli.ding_calls == []


def test_start_writes_row_and_dings_capped_after_sleep(cli, rows):
    cli.elapsed_s = 3 * 3600  # lid closed past the deadline
    cli.run(["start", "work", "25"])
    (row,) = rows()
    assert row["actual_min"] == pytest.approx(25.0)
    assert row["completed"] == 1


def test_start_writes_row_and_dings_caffeinate_first(cli):
    cli.run(["start", "work", "25"])
    assert cli.caffeinate_pids == [os.getpid()]
    assert cli.events.index("caffeinate") < cli.events.index("timer")


# --- 15 ------------------------------------------------------------------
def test_log_yesterday_shows_in_week_and_garden(cli, rows, day_row, capsys):
    assert cli.run(["log", "learning", "30", "--date", YESTERDAY.isoformat()]) == 0
    assert [p.strip() for p in cli.prompts] == ['New tag "learning"? [y/N]']
    (row,) = rows()
    assert {k: row[k] for k in ("tag", "planned_min", "completed", "source")} == {
        "tag": "learning", "planned_min": 30, "completed": 1, "source": "manual"}
    assert row["actual_min"] == pytest.approx(30.0)
    assert row["start"][:10] == YESTERDAY.isoformat()
    capsys.readouterr()

    cli.run(_week_args(YESTERDAY))
    line = day_row(capsys.readouterr().out, YESTERDAY, weekday_ok=True)
    assert line is not None and "0.5" in line

    cli.run(["garden"])
    line = day_row(capsys.readouterr().out, YESTERDAY)
    assert line is not None and "🍄" in line


def test_log_yesterday_at_sets_start_time(cli, rows):
    assert cli.run(["log", "work", "45", "--date", YESTERDAY.isoformat(), "--at", "14:30"]) == 0
    (row,) = rows()
    assert row["start"].startswith(f"{YESTERDAY.isoformat()}T14:30")
    assert row["actual_min"] == pytest.approx(45.0)


# --- 16 ------------------------------------------------------------------
@pytest.mark.parametrize("given, expected", [("w", "work"), ("l", "l"), ("work", "work"),
                                             ("writing", "writing"), ("W", "W"), ("ww", "ww")])
def test_new_tag_prompt_and_shortcuts_resolve(given, expected):
    assert bonsai.resolve_tag(given) == expected


def test_new_tag_prompt_and_shortcuts_log_declined(cli, rows, tags):
    cli.answer = False
    code = cli.run(["log", "learnign", "30"])
    assert [p.strip() for p in cli.prompts] == ['New tag "learnign"? [y/N]']
    assert code != 0
    assert rows() == []
    assert "learnign" not in tags()


def test_new_tag_prompt_and_shortcuts_start_declined(cli, rows, tags):
    cli.run(["start", "writing", "25"])
    cli.answer = False
    code = cli.run(["start", "learnign", "40"])
    assert [p.strip() for p in cli.prompts] == ['New tag "writing"? [y/N]', 'New tag "learnign"? [y/N]']
    assert code != 0
    assert cli.timer_calls == [(25, "writing")]
    assert len(rows()) == 1
    assert "learnign" not in tags()
    cli.run([])  # remembered tag/minutes unchanged by the declined start
    assert cli.timer_calls[-1] == (25, "writing")


def test_new_tag_prompt_and_shortcuts_never_prompt(cli, add_session):
    for argv in (["start", "work"], ["start", "w"], ["log", "w", "30"], ["log", "work", "30"]):
        cli.run(argv)
    assert cli.prompts == []
    assert [t for _, t in cli.timer_calls] == ["work", "work"]

    add_session("writing", TODAY, emoji="🌻")
    cli.run(["start", "writing"])
    cli.run(["log", "writing", "30"])
    assert cli.prompts == []


# --- 17 ------------------------------------------------------------------
def _three_sessions(cli):
    cli.run(["log", "work", "30", "--date", TODAY.isoformat()])
    cli.run(["log", "learning", "45", "--date", TODAY.isoformat()])
    # Last written, but backdated: highest id, not latest start.
    cli.run(["log", "work", "50", "--date", (TODAY - timedelta(days=10)).isoformat()])


def test_undo_last_only(cli, rows, capsys):
    _three_sessions(cli)
    before = rows()
    capsys.readouterr()
    cli.prompts.clear()  # ignore new-tag prompts from setup
    seen = {}
    cli.on_confirm = lambda prompt: seen.setdefault("out", capsys.readouterr().out + prompt)
    cli.answer = True

    assert cli.run(["undo"]) == 0
    after = rows()
    assert after == before[:2]
    assert len(cli.prompts) == 1
    assert "50" in seen["out"] and "work" in seen["out"]  # session shown before asking


def test_undo_last_only_declined(cli, rows):
    _three_sessions(cli)
    before = rows()
    cli.answer = False
    cli.run(["undo"])
    assert rows() == before


def test_undo_last_only_empty(cli, rows, capsys):
    assert cli.run(["undo"]) == 0
    assert capsys.readouterr().out.strip()
    assert cli.prompts == []
    assert rows() == []


# --- 18 ------------------------------------------------------------------
HEADER = ["id", "tag", "start", "end", "planned_min", "actual_min", "completed", "source"]


def test_export_csv(cli, rows, add_session, tmp_path, capsys):
    cli.run(["log", "work", "90", "--date", TODAY.isoformat(), "--at", "08:00"])
    cli.run(["log", "learning", "30", "--date", TODAY.isoformat(), "--at", "10:00"])
    add_session("work", TODAY, "11:00", actual_min=12, completed=0, planned_min=30)

    target = tmp_path / "out.csv"
    assert cli.run(["export", str(target)]) == 0
    with target.open(newline="") as f:
        data = list(csv.reader(f))
    assert data[0] == HEADER
    body = [dict(zip(HEADER, r)) for r in data[1:]]
    assert len(body) == len(rows()) == 3
    assert sorted(int(r["id"]) for r in body) == [r["id"] for r in rows()]
    assert sorted(r["completed"] for r in body) == ["0", "1", "1"]

    csv_hours = sum(float(r["actual_min"]) for r in body) / 60
    assert csv_hours == pytest.approx(132 / 60)
    capsys.readouterr()
    cli.run(["week"])
    totals = _totals_line(capsys.readouterr().out)
    # work 102 min = 1.7h, life 30 min = 0.5h; 1.7 + 0.5 == CSV hours
    assert any("1.7" in ln and "0.5" in ln for ln in totals)


def test_export_csv_default_path(cli):
    cli.run(["log", "work", "30", "--date", TODAY.isoformat()])
    assert cli.run(["export"]) == 0
    target = Path(os.environ["HOME"]) / f"bonsai-export-{TODAY.isoformat()}.csv"
    assert target.exists()
    with target.open(newline="") as f:
        data = list(csv.reader(f))
    assert data[0] == HEADER and len(data) == 2


def test_export_csv_empty_has_header(cli, tmp_path):
    target = tmp_path / "empty.csv"
    assert cli.run(["export", str(target)]) == 0
    with target.open(newline="") as f:
        assert list(csv.reader(f)) == [HEADER]


# --- 19 ------------------------------------------------------------------
LAST_MON = MONDAY - timedelta(days=7)
LAST_WED = LAST_MON + timedelta(days=2)


@pytest.fixture
def two_weeks(add_session):
    add_session("work", MONDAY, "09:00", actual_min=60)
    add_session("learning", MONDAY, "11:00", actual_min=30, emoji="🍄")
    add_session("work", MONDAY + timedelta(days=1), "09:00", actual_min=18, completed=0, planned_min=30)
    add_session("work", LAST_WED, "09:00", actual_min=120)
    add_session("writing", LAST_WED, "13:00", actual_min=90, emoji="🌻")


def test_week_last_and_detail_this_week(two_weeks, cli, day_row, capsys):
    assert cli.run(["week"]) == 0
    out = capsys.readouterr().out
    for i in range(7):
        assert day_row(out, MONDAY + timedelta(days=i), weekday_ok=True) is not None, i
    mon = day_row(out, MONDAY, weekday_ok=True)
    assert "1.0" in mon and "0.5" in mon
    assert "0.3" in day_row(out, MONDAY + timedelta(days=1), weekday_ok=True)  # incomplete counts
    assert any("1.3" in ln and "0.5" in ln for ln in _totals_line(out))
    assert "40" in out
    assert "learning" not in out and "writing" not in out  # no per-tag columns by default


def test_week_last_and_detail_last(two_weeks, cli, day_row, capsys):
    assert cli.run(["week", "--last"]) == 0
    out = capsys.readouterr().out
    for i in range(7):
        assert day_row(out, LAST_MON + timedelta(days=i), weekday_ok=True) is not None, i
    wed = day_row(out, LAST_WED, weekday_ok=True)
    assert "2.0" in wed and "1.5" in wed
    assert any("2.0" in ln and "1.5" in ln for ln in _totals_line(out))
    assert not any("1.3" in ln for ln in _totals_line(out))


def test_week_last_and_detail_detail(two_weeks, cli, capsys):
    assert cli.run(["week", "--detail"]) == 0
    out = capsys.readouterr().out
    assert "learning" in out and "writing" not in out


def test_week_last_and_detail_combined(two_weeks, cli, day_row, capsys):
    assert cli.run(["week", "--last", "--detail"]) == 0
    out = capsys.readouterr().out
    assert "writing" in out and "learning" not in out
    assert "2.0" in day_row(out, LAST_WED, weekday_ok=True)


# --- 20 ------------------------------------------------------------------
def test_today_output(cli, add_session, capsys):
    add_session("work", TODAY, "09:00", actual_min=60)
    add_session("learning", TODAY, "11:00", actual_min=30, emoji="🍄")
    add_session("learning", TODAY, "13:00", actual_min=15)
    add_session("work", YESTERDAY, "09:00", actual_min=90)

    assert cli.run(["today"]) == 0
    out = capsys.readouterr().out
    row = [ln for ln in out.splitlines() if "🌵 🌵   🍄 🍄" in ln]
    assert row, out
    assert row[0].count("🌵") == 2 and row[0].count("🍄") == 2
    for t in ("09:00", "11:00", "13:00"):
        assert t in out  # each of today's sessions is listed
    learning_lines = [ln for ln in out.splitlines() if "learning" in ln]
    assert any(re.search(r"(?<![\d.])(45|0\.8|0\.75)(?![\d])", ln) for ln in learning_lines)


# --- 21 ------------------------------------------------------------------
def _prev_weekdays(n):
    days, d = [], TODAY
    while len(days) < n:
        d -= timedelta(days=1)
        if d.weekday() < 5:
            days.append(d)
    return days


def test_garden_output(cli, add_session, day_row, capsys):
    old_mon = MONDAY - timedelta(weeks=10)
    for i in range(4):  # 4-weekday streak, 4 plants, all older than 4 weeks
        add_session("learning", old_mon + timedelta(days=i), actual_min=30, emoji="🍄")
    recent = _prev_weekdays(3)
    for d in recent:  # current streak 3 (today has none yet), 2 plants each
        add_session("work", d, actual_min=60)
    add_session("writing", TODAY, actual_min=90, completed=0, emoji="🌻")  # no plants

    assert cli.run(["garden"]) == 0
    out = capsys.readouterr().out
    first = MONDAY - timedelta(weeks=3)
    day_lines = []
    for i in range(28):
        line = day_row(out, first + timedelta(days=i))
        assert line is not None, first + timedelta(days=i)
        day_lines.append(line)
    assert len(set(day_lines)) == 28
    for d in recent:
        assert day_row(out, d).count("🌵") == 2
    assert day_row(out, old_mon) is None

    lines = out.splitlines()
    header = "\n".join(lines[: lines.index(day_lines[0])])
    nums = set(re.findall(r"(?<![\d.\-/:])\d+(?![\d.\-/:])", header))
    assert {"3", "4", "10"} <= nums, header

    legend = [ln for ln in lines if re.search(r"🌵\s+work", ln)]
    assert legend, out
    leg = legend[-1]
    assert re.search(r"🍄\s+learning", leg) and re.search(r"🌻\s+writing", leg)
    assert leg.index("🌵") < min(leg.index("🍄"), leg.index("🌻"))


# --- 22 ------------------------------------------------------------------
def test_cap_warning_on_work_start(cli, add_session, capsys):
    add_session("work", MONDAY, "00:01", actual_min=38 * 60, planned_min=38 * 60)
    assert cli.run(["start", "w", "25"]) == 0
    out = capsys.readouterr().out
    assert bonsai.cap_warning(38.0).strip() in out
    assert cli.timer_calls == [(25, "work")]


def test_cap_warning_on_work_start_not_for_life(cli, add_session, capsys):
    add_session("work", MONDAY, "00:01", actual_min=38 * 60, planned_min=38 * 60)
    assert cli.run(["start", "learning", "25"]) == 0
    out = capsys.readouterr().out
    assert bonsai.cap_warning(38.0).strip() not in out
    assert cli.timer_calls == [(25, "learning")]


def test_cap_warning_on_work_start_below_threshold(cli, add_session, capsys):
    add_session("work", MONDAY, "00:01", actual_min=37 * 60, planned_min=37 * 60)
    cli.run(["start", "w", "25"])
    out_below = capsys.readouterr().out
    assert bonsai.cap_warning(38.0).strip() not in out_below
    assert cli.timer_calls == [(25, "work")]


# --- 23 ------------------------------------------------------------------
@pytest.mark.parametrize("argv", [["start", "work", "1.5"], ["log", "work", "abc"],
                                  ["start", "work", "0"], ["log", "work", "-5"],
                                  ["log", "work", "0"], ["start", "work", "abc"]])
def test_minutes_must_be_positive_int(argv, cli, rows):
    assert cli.run(argv) == 2
    assert rows() == []
    assert cli.timer_calls == []


def test_minutes_must_be_positive_int_one_is_ok(cli, rows):
    assert cli.run(["start", "work", "1"]) == 0
    assert cli.timer_calls == [(1, "work")]
    assert cli.run(["log", "work", "1"]) == 0
    assert len(rows()) == 2


# --- 24 ------------------------------------------------------------------
def test_start_digits_only_means_minutes(cli):
    cli.run(["start", "writing", "30"])
    prompts_before = len(cli.prompts)
    cli.run(["start", "25"])
    assert cli.timer_calls[-1] == (25, "writing")
    assert len(cli.prompts) == prompts_before


def test_start_digits_only_means_minutes_empty_db(cli):
    cli.run(["start", "25"])
    assert cli.timer_calls == [(25, "work")]
    assert cli.prompts == []


# --- log --start/--end ---------------------------------------------------
def test_log_start_end_computes_minutes(cli, rows):
    assert cli.run(["log", "w", "--date", YESTERDAY.isoformat(),
                    "--start", "09:15", "--end", "11:45"]) == 0
    (row,) = rows()
    assert row["tag"] == "work"
    assert row["start"].startswith(f"{YESTERDAY.isoformat()}T09:15")
    assert row["end"].startswith(f"{YESTERDAY.isoformat()}T11:45")
    assert row["actual_min"] == pytest.approx(150.0)
    assert row["planned_min"] == 150


def test_log_start_with_minutes_works_like_at(cli, rows):
    assert cli.run(["log", "work", "30", "--date", YESTERDAY.isoformat(), "--start", "14:00"]) == 0
    (row,) = rows()
    assert row["start"].startswith(f"{YESTERDAY.isoformat()}T14:00")
    assert row["actual_min"] == pytest.approx(30.0)


@pytest.mark.parametrize("argv", [
    ["log", "work"],                                          # no minutes, no range
    ["log", "work", "--end", "11:00"],                        # end without start
    ["log", "work", "30", "--start", "09:00", "--end", "10:00"],  # both
    ["log", "work", "--start", "11:00", "--end", "11:00"],    # zero length
    ["log", "work", "--start", "11:00", "--end", "09:00"],    # end before start
])
def test_log_start_end_rejects_bad_input(argv, cli, rows):
    assert cli.run(argv) == 2
    assert rows() == []
