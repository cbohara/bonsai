# /// script
# requires-python = ">=3.12"
# dependencies = ["rich"]
# ///
"""bonsai: terminal Pomodoro + time tracker with a garden."""

import argparse
import csv
import math
import os
import sqlite3
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from datetime import time as dtime
from pathlib import Path

from rich import box
from rich.console import Console, Group
from rich.live import Live
from rich.markup import escape
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text

SOUND_FILE = "/System/Library/Sounds/Glass.aiff"
DING_REPEATS = 3
DING_GAP_S = 1.5
VOLUME = 1.0
DEFAULT_MINUTES = 30
WORK_CAP_H = 40
DEFAULT_EMOJIS = ["🍄", "🌻", "🌷", "🌼", "🌸", "🍀", "🌺", "🪻"]

WORK_EMOJI = "🌵"
WORK_COLOR = "green"
LIFE_COLOR = "light_coral"
TICK_S = 0.25

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
  id            INTEGER PRIMARY KEY,
  tag           TEXT NOT NULL,
  start         TEXT NOT NULL,
  end           TEXT NOT NULL,
  planned_min   INTEGER NOT NULL,
  actual_min    REAL NOT NULL,
  completed     INTEGER NOT NULL,
  source        TEXT NOT NULL DEFAULT 'timer'
);
CREATE TABLE IF NOT EXISTS tags (name TEXT PRIMARY KEY, emoji TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
"""
SESSION_COLS = ["id", "tag", "start", "end", "planned_min", "actual_min", "completed", "source"]

# 3-row block font for the live countdown.
BIG_DIGITS = {
    "0": ("█▀█", "█ █", "▀▀▀"), "1": (" ▀█", "  █", "  ▀"), "2": ("▀▀█", "█▀▀", "▀▀▀"),
    "3": ("▀▀█", " ▀█", "▀▀▀"), "4": ("█ █", "▀▀█", "  ▀"), "5": ("█▀▀", "▀▀█", "▀▀▀"),
    "6": ("█▀▀", "█▀█", "▀▀▀"), "7": ("▀▀█", "  █", "  ▀"), "8": ("█▀█", "█▀█", "▀▀▀"),
    "9": ("█▀█", "▀▀█", "▀▀▀"), ":": (" ", "▀", "▀"),
}


# --- pure logic -------------------------------------------------------------

def plants_for_session(actual_min: float, completed: bool) -> int:
    if not completed:
        return 0
    return max(1, int(actual_min // 30))


def plant_stage(progress: float, emoji: str, stopped: bool = False) -> str:
    if stopped:
        return "🥀"
    if progress < 0.25:
        return "·"
    if progress < 0.5:
        return "🌱"
    if progress < 0.9:
        return "🌿"
    return emoji


def week_bounds(d: date) -> tuple[date, date]:
    monday = d - timedelta(days=d.weekday())
    return monday, monday + timedelta(days=6)


def session_date(start_iso: str) -> date:
    return date.fromisoformat(start_iso[:10])


def prev_weekday(d: date) -> date:
    d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def current_streak(completed_dates: set[date], today: date) -> int:
    d = today if today in completed_dates else today - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    n = 0
    while d in completed_dates:
        n += 1
        d = prev_weekday(d)
    return n


def best_streak(completed_dates: set[date]) -> int:
    runs = {}
    for d in sorted(x for x in completed_dates if x.weekday() < 5):
        runs[d] = runs.get(prev_weekday(d), 0) + 1
    return max(runs.values(), default=0)


def next_default_emoji(used: list[str]) -> str:
    for e in DEFAULT_EMOJIS:
        if e not in used:
            return e
    return DEFAULT_EMOJIS[len(used) % len(DEFAULT_EMOJIS)]


def validate_tag_emoji(name: str, emoji: str) -> None:
    if name == "work":
        raise ValueError("work is always 🌵 and can't be changed")
    if emoji == WORK_EMOJI:
        raise ValueError("🌵 is reserved for work")


def garden_row(plants: list[tuple[str, int]], emojis: dict[str, str]) -> str:
    work = [WORK_EMOJI] * sum(n for tag, n in plants if tag == "work")
    life = {}
    for tag, n in plants:
        if tag != "work":
            life[tag] = life.get(tag, 0) + n
    life_plants = [emojis.get(tag, "🌱") for tag, n in life.items() for _ in range(n)]
    return "   ".join(part for part in (" ".join(work), " ".join(life_plants)) if part)


def bar_color(work_hours: float) -> str:
    if work_hours < 32:
        return "green"
    if work_hours < 38:
        return "yellow"
    return "red"


def cap_warning(work_hours: float) -> str | None:
    if work_hours < 38:
        return None
    return f"Heads-up: {work_hours:.1f}h of work this week, cap is {WORK_CAP_H}h."


def actual_minutes(start_ts: float, end_ts: float, planned_min: int) -> float:
    return float(min(planned_min, (end_ts - start_ts) / 60))


def resolve_tag(tag: str) -> str:
    return {"w": "work", "l": "learning"}.get(tag, tag)


# --- DB layer ---------------------------------------------------------------

def db_path() -> Path:
    env = os.environ.get("BONSAI_DB")
    return Path(env) if env else Path.home() / ".bonsai" / "bonsai.db"


def init_db(path: Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    return conn


def get_tags(conn) -> dict[str, str]:
    return dict(conn.execute("SELECT name, emoji FROM tags ORDER BY rowid"))


def emoji_for(tag: str, tags: dict[str, str]) -> str:
    return WORK_EMOJI if tag == "work" else tags.get(tag, "🌱")


def ensure_tag(conn, name: str) -> None:
    if name == "work":
        return
    tags = get_tags(conn)
    if name in tags:
        return
    conn.execute("INSERT INTO tags (name, emoji) VALUES (?, ?)",
                 (name, next_default_emoji(list(tags.values()))))
    conn.commit()


def set_tag_emoji(conn, name: str, emoji: str) -> None:
    validate_tag_emoji(name, emoji)
    conn.execute("INSERT INTO tags (name, emoji) VALUES (?, ?)"
                 " ON CONFLICT(name) DO UPDATE SET emoji = excluded.emoji", (name, emoji))
    conn.commit()


def get_setting(conn, key: str) -> str | None:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def set_setting(conn, key: str, value: str) -> None:
    conn.execute("INSERT INTO settings (key, value) VALUES (?, ?)"
                 " ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))
    conn.commit()


def fetch_sessions(conn, first: date | None = None, last: date | None = None) -> list[dict]:
    sql = f"SELECT {', '.join(SESSION_COLS)} FROM sessions"
    params = ()
    if first is not None:
        sql += " WHERE substr(start, 1, 10) BETWEEN ? AND ?"
        params = (first.isoformat(), last.isoformat())
    sql += " ORDER BY start, id"
    return [dict(zip(SESSION_COLS, r)) for r in conn.execute(sql, params)]


def last_session(conn) -> dict | None:
    row = conn.execute(f"SELECT {', '.join(SESSION_COLS)} FROM sessions ORDER BY id DESC LIMIT 1").fetchone()
    return dict(zip(SESSION_COLS, row)) if row else None


def delete_session(conn, session_id: int) -> None:
    conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()


def add_session(conn, tag: str, start: datetime, end: datetime, planned_min: int,
                actual_min: float, completed: bool, source: str) -> None:
    conn.execute(
        "INSERT INTO sessions (tag, start, end, planned_min, actual_min, completed, source)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (tag, start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds"),
         planned_min, actual_min, int(completed), source))
    conn.commit()


def hours(sessions: list[dict], group: str | None = None) -> float:
    """Hours over sessions; group is 'work', 'life', a tag name, or None for all."""
    def match(tag):
        if group is None:
            return True
        if group == "life":
            return tag != "work"
        return tag == group
    return sum(s["actual_min"] for s in sessions if match(s["tag"])) / 60


def day_plants(sessions: list[dict]) -> list[tuple[str, int]]:
    return [(s["tag"], plants_for_session(s["actual_min"], s["completed"])) for s in sessions]


# --- side-effect seams ------------------------------------------------------

def big_time(seconds: float) -> Text:
    mm, ss = divmod(max(0, math.ceil(seconds)), 60)
    chars = f"{mm:02d}:{ss:02d}"
    rows = [" ".join(BIG_DIGITS[c][i] for c in chars) for i in range(3)]
    return Text("\n".join(rows), style="bold")


def timer_view(tag: str, emoji: str, remaining: float, total: float, stopped: bool = False) -> Panel:
    progress = min(1.0, max(0.0, 1 - remaining / total))
    color = WORK_COLOR if tag == "work" else LIFE_COLOR
    return Panel(
        Group(
            Text(tag, style=f"bold {color}"),
            Text(""),
            big_time(remaining),
            Text(""),
            ProgressBar(total=total, completed=total - remaining, width=40, complete_style=color),
            Text(""),
            Text(plant_stage(progress, emoji, stopped)),
        ),
        title="bonsai", expand=False, padding=(1, 4),
    )


def run_timer(planned_min: int, tag: str, emoji: str,
              clock=time.time, sleep=time.sleep) -> tuple[float, float, bool]:
    total = planned_min * 60
    start_ts = clock()
    deadline = start_ts + total
    now, completed = start_ts, False
    with Live(timer_view(tag, emoji, total, total), console=Console(), auto_refresh=False) as live:
        try:
            while True:
                now = clock()
                if now >= deadline:
                    completed = True
                    break
                live.update(timer_view(tag, emoji, deadline - now, total), refresh=True)
                sleep(TICK_S)
        except KeyboardInterrupt:
            now = clock()
        live.update(timer_view(tag, emoji, max(0.0, deadline - now), total, stopped=not completed),
                    refresh=True)
    return start_ts, now, completed


def ding(tag: str, minutes: int) -> None:
    try:
        for i in range(DING_REPEATS):
            if i:
                time.sleep(DING_GAP_S)
            subprocess.run(["afplay", "-v", str(VOLUME), SOUND_FILE], check=True)
    except (OSError, subprocess.CalledProcessError) as e:
        print(f"warning: afplay failed ({e}); using notification and bell", file=sys.stderr)
    text = f"{tag.capitalize()} session done — {minutes} min"
    try:
        subprocess.run(["osascript", "-e", f'display notification "{text}" with title "bonsai"'], check=False)
    except OSError as e:
        print(f"warning: notification failed ({e})", file=sys.stderr)
    sys.stdout.write("\a")
    sys.stdout.flush()


def start_caffeinate(pid: int) -> subprocess.Popen:
    return subprocess.Popen(["caffeinate", "-i", "-w", str(pid)])


def confirm(prompt: str) -> bool:
    try:
        return input(prompt + " ").strip().lower() in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        print()
        return False


# --- commands ---------------------------------------------------------------

def make_console() -> Console:
    return Console(highlight=False, emoji=False)


def needs_confirm(conn, tag: str) -> bool:
    return tag not in ("work", "learning") and tag not in get_tags(conn)


def new_tag_ok(conn, tag: str) -> bool:
    if needs_confirm(conn, tag) and not confirm(f'New tag "{tag}"? [y/N]'):
        print("Cancelled.")
        return False
    ensure_tag(conn, tag)
    return True


def cmd_start(conn, args) -> int:
    console = make_console()
    tag = resolve_tag(args.tag) if args.tag else get_setting(conn, "last_tag") or "work"
    minutes = args.minutes or int(get_setting(conn, "last_minutes") or DEFAULT_MINUTES)
    if not new_tag_ok(conn, tag):
        return 1
    set_setting(conn, "last_tag", tag)
    set_setting(conn, "last_minutes", str(minutes))

    if tag == "work":
        monday, sunday = week_bounds(date.today())
        warning = cap_warning(hours(fetch_sessions(conn, monday, sunday), "work"))
        if warning:
            console.print(escape(warning), style="yellow")

    emoji = emoji_for(tag, get_tags(conn))
    caffeinate = start_caffeinate(os.getpid())
    try:
        start_ts, end_ts, completed = run_timer(minutes, tag, emoji)
        actual = actual_minutes(start_ts, end_ts, minutes)
        add_session(conn, tag, datetime.fromtimestamp(start_ts).astimezone(),
                    datetime.fromtimestamp(end_ts).astimezone(), minutes, actual, completed, "timer")
        if completed:
            ding(tag, minutes)
    finally:
        caffeinate.terminate()

    if completed:
        n = plants_for_session(actual, True)
        console.print(f"{emoji} {escape(tag)}: {actual:.0f} min done, {n} plant{'s' * (n != 1)} planted.")
    else:
        console.print(f"🥀 {escape(tag)}: stopped after {actual:.1f} of {minutes} min. Nothing planted.")
    return 0


def cmd_log(conn, args) -> int:
    tag = resolve_tag(args.tag)
    if not new_tag_ok(conn, tag):
        return 1
    start = datetime.combine(args.date or date.today(), args.at).astimezone()
    end = start + timedelta(minutes=args.minutes)
    add_session(conn, tag, start, end, args.minutes, float(args.minutes), True, "manual")
    emoji = emoji_for(tag, get_tags(conn))
    make_console().print(f"Logged {emoji} {escape(tag)}: {args.minutes} min on {start:%Y-%m-%d %H:%M}.")
    return 0


def cmd_today(conn, args) -> int:
    console = make_console()
    today = date.today()
    sessions = fetch_sessions(conn, today, today)
    tags = get_tags(conn)
    console.print(f"[bold]Today[/bold] {today:%a %Y-%m-%d}")
    if not sessions:
        console.print("No sessions today.")
        return 0
    for s in sessions:
        status = {"manual": "logged"}.get(s["source"], "done" if s["completed"] else "stopped")
        console.print(f"  {s['start'][11:16]}  {emoji_for(s['tag'], tags)} {escape(s['tag'])}"
                      f"  {s['actual_min']:.0f} min  {status}")
    console.print()
    for tag in dict.fromkeys(s["tag"] for s in sessions):
        h = hours(sessions, tag)
        color = WORK_COLOR if tag == "work" else LIFE_COLOR
        console.print(f"  {emoji_for(tag, tags)} {escape(tag)}  [{color}]{h * 60:.0f} min ({h:.1f}h)[/]")
    console.print(f"  [{WORK_COLOR}]work {hours(sessions, 'work'):.1f}h[/]"
                  f"  [{LIFE_COLOR}]life {hours(sessions, 'life'):.1f}h[/]")
    row = garden_row(day_plants([s for s in sessions if s["completed"]]), tags)
    console.print()
    console.print(f"  {row or 'nothing planted yet'}", soft_wrap=True)
    return 0


def cmd_week(conn, args) -> int:
    console = make_console()
    monday, sunday = week_bounds(date.today())
    if args.last:
        monday, sunday = monday - timedelta(days=7), sunday - timedelta(days=7)
    sessions = fetch_sessions(conn, monday, sunday)
    life_tags = list(dict.fromkeys(s["tag"] for s in sessions if s["tag"] != "work")) if args.detail else []

    table = Table(title=f"Week {monday:%Y-%m-%d} – {sunday:%Y-%m-%d}", box=box.SIMPLE_HEAD)
    table.add_column("Day")
    table.add_column("Work", justify="right", style=WORK_COLOR)
    table.add_column("Life", justify="right", style=LIFE_COLOR)
    for tag in life_tags:
        table.add_column(tag, justify="right", style=LIFE_COLOR)

    def cells(ss):
        return [f"{hours(ss, 'work'):.1f}", f"{hours(ss, 'life'):.1f}"] + [
            f"{hours(ss, t):.1f}" for t in life_tags]

    for i in range(7):
        d = monday + timedelta(days=i)
        table.add_row(f"{d:%a %Y-%m-%d}", *cells([s for s in sessions if session_date(s["start"]) == d]))
    table.add_section()
    table.add_row("Total", *cells(sessions))
    console.print(table)

    work_h = hours(sessions, "work")
    filled = min(WORK_CAP_H, round(work_h))
    bar = "█" * filled + "░" * (WORK_CAP_H - filled)
    console.print(f"Work {work_h:.1f}h / {WORK_CAP_H}h  [{bar_color(work_h)}]{bar}[/]")
    return 0


def cmd_garden(conn, args) -> int:
    console = make_console()
    today = date.today()
    all_sessions = fetch_sessions(conn)
    done = [s for s in all_sessions if s["completed"]]
    dates = {session_date(s["start"]) for s in done}
    total_plants = sum(n for _, n in day_plants(done))
    tags = get_tags(conn)

    console.print(f"[bold]Garden[/bold]  streak {current_streak(dates, today)}"
                  f"  ·  best {best_streak(dates)}  ·  {total_plants} plants")
    first = week_bounds(today)[0] - timedelta(weeks=3)
    sessions = fetch_sessions(conn, first, first + timedelta(days=27))
    table = Table(box=box.SIMPLE_HEAD)
    table.add_column("Day")
    table.add_column("Plants")
    table.add_column("Hours", justify="right")
    for i in range(28):
        d = first + timedelta(days=i)
        if i and d.weekday() == 0:
            table.add_section()
        day = [s for s in sessions if session_date(s["start"]) == d]
        row = garden_row(day_plants([s for s in day if s["completed"]]), tags)
        table.add_row(f"{d:%a %Y-%m-%d}", row, f"{hours(day):.1f}")
    console.print(table)
    legend = [f"{WORK_EMOJI} work"] + [f"{e} {escape(name)}" for name, e in tags.items()]
    console.print("  ".join(legend), soft_wrap=True)
    return 0


def cmd_tag(conn, args) -> int:
    console = make_console()
    tags = get_tags(conn)
    if args.name and args.emoji:
        try:
            set_tag_emoji(conn, args.name, args.emoji)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        console.print(f"{args.emoji}  {escape(args.name)}  life")
        return 0
    rows = [("work", WORK_EMOJI, "work")] + [(n, e, "life") for n, e in tags.items()]
    if args.name:
        rows = [r for r in rows if r[0] == args.name]
        if not rows:
            print(f'error: no tag named "{args.name}"', file=sys.stderr)
            return 1
    for name, emoji, group in rows:
        console.print(f"{emoji}  {escape(name)}  {group}")
    return 0


def cmd_undo(conn, args) -> int:
    s = last_session(conn)
    if s is None:
        print("No sessions to undo.")
        return 0
    status = "completed" if s["completed"] else "stopped"
    print(f"#{s['id']}  {s['start'][:16].replace('T', ' ')}  {s['tag']}"
          f"  {s['actual_min']:.0f} of {s['planned_min']} min  {status}  ({s['source']})")
    if confirm("Delete this session? [y/N]"):
        delete_session(conn, s["id"])
        print("Deleted.")
    else:
        print("Kept.")
    return 0


def cmd_export(conn, args) -> int:
    target = Path(args.file) if args.file else Path.home() / f"bonsai-export-{date.today().isoformat()}.csv"
    rows = conn.execute(f"SELECT {', '.join(SESSION_COLS)} FROM sessions ORDER BY id").fetchall()
    with target.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(SESSION_COLS)
        writer.writerows(rows)
    print(f"Exported {len(rows)} sessions to {target}")
    return 0


def cmd_test_ding(conn, args) -> int:
    ding("work", DEFAULT_MINUTES)
    return 0


# --- CLI --------------------------------------------------------------------

def minutes_arg(s: str) -> int:
    if not (s.isascii() and s.isdigit()) or int(s) < 1:
        raise argparse.ArgumentTypeError(f"minutes must be a whole number >= 1, got {s!r}")
    return int(s)


def at_arg(s: str) -> dtime:
    try:
        return datetime.strptime(s, "%H:%M").time()
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected HH:MM, got {s!r}") from None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bonsai", description="Pomodoro + time tracker with a garden.")
    sub = parser.add_subparsers(dest="cmd")

    p = sub.add_parser("start", help="start a session (default command)")
    p.add_argument("tag", nargs="?", help="tag (w = work, l = learning) or minutes")
    p.add_argument("minutes", nargs="?", type=minutes_arg)

    sub.add_parser("today", help="today's sessions and garden row")

    p = sub.add_parser("week", help="hours per day this week")
    p.add_argument("--last", action="store_true", help="previous Mon–Sun week")
    p.add_argument("--detail", action="store_true", help="one column per life tag")

    sub.add_parser("garden", help="last 4 weeks as a garden")

    p = sub.add_parser("log", help="add a session you forgot to track")
    p.add_argument("tag")
    p.add_argument("minutes", type=minutes_arg)
    p.add_argument("--date", type=date.fromisoformat, help="YYYY-MM-DD (default today)")
    p.add_argument("--at", type=at_arg, default=dtime(12, 0), help="HH:MM start time (default 12:00)")

    p = sub.add_parser("tag", help="list tags or set a life tag's emoji")
    p.add_argument("name", nargs="?")
    p.add_argument("emoji", nargs="?")

    sub.add_parser("undo", help="delete the most recent session")

    p = sub.add_parser("export", help="CSV of all sessions")
    p.add_argument("file", nargs="?")

    sub.add_parser("test-ding", help="play the end-of-session ding now")
    return parser


COMMANDS = {
    "start": cmd_start, "today": cmd_today, "week": cmd_week, "garden": cmd_garden,
    "log": cmd_log, "tag": cmd_tag, "undo": cmd_undo, "export": cmd_export,
    "test-ding": cmd_test_ding,
}


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.cmd is None:
        args = parser.parse_args(["start"])
    if args.cmd == "start" and args.tag and args.tag.isascii() and args.tag.isdigit():
        if args.minutes is not None:
            parser.error("give minutes once: bonsai start [tag] [minutes]")
        try:
            args.minutes = minutes_arg(args.tag)
        except argparse.ArgumentTypeError as e:
            parser.error(str(e))
        args.tag = None
    conn = init_db(db_path())
    try:
        return COMMANDS[args.cmd](conn, args)
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
