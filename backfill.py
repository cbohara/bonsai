# /// script
# requires-python = ">=3.12"
# dependencies = ["rich", "pdfplumber"]
# ///
"""One-time backfill of Toggl history into bonsai's database. Rules: docs/BACKFILL.md.

Usage:
  uv run backfill.py pdf <report.pdf> <out.csv>     # Toggl "Detailed report" PDF -> CSV
  uv run backfill.py import <file.csv> [--dry-run]  # CSV -> bonsai
"""

import argparse
import csv
import re
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

import bonsai

# --- PDF -> CSV --------------------------------------------------------------

# Long descriptions wrap: text can appear before the time range and before the date.
TIME_RE = re.compile(r"^(?P<pre>.*?)\s*(?:•\s*)?(?P<t1>\d{1,2}:\d{2} [AP]M) - (?P<t2>\d{1,2}:\d{2} [AP]M)$")
DATE_RE = re.compile(r"^(?P<post>.*?)\s*(?P<d>\d{2}/\d{2}/\d{4})$")
ROW_RE = re.compile(
    r"^(?P<desc>.*?)\s*(?P<dur>\d+:\d{2}:\d{2}|-)\s+(?P<member>Charlie O'Hara)\s+(?P<rest>.*)$"
)


def dur_seconds(d):
    if d == "-":
        return 0
    h, m, s = (int(x) for x in d.split(":"))
    return h * 3600 + m * 60 + s


def parse(pdf_path):
    lines = []
    import pdfplumber  # only needed here; keeps tests and `import` free of it

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            lines += [ln.strip() for ln in (page.extract_text() or "").splitlines()]

    entries, i = [], 0
    while i < len(lines):
        m = TIME_RE.match(lines[i])
        if not m:
            i += 1
            continue
        start_s, pre = m["t1"], m["pre"]
        row = ROW_RE.match(lines[i + 1]) if i + 1 < len(lines) else None
        date = DATE_RE.match(lines[i + 2]) if i + 2 < len(lines) else None
        if not (row and date):
            raise ValueError(f"Unexpected layout near line {i}: {lines[i:i+3]}")
        rest = row["rest"].rsplit(" ", 1)  # project may contain spaces; tags is last token
        project, tags = (rest[0], rest[1]) if len(rest) == 2 else (rest[0], "-")
        day = datetime.strptime(date["d"], "%m/%d/%Y")
        start = datetime.strptime(f"{date['d']} {start_s}", "%m/%d/%Y %I:%M %p")
        secs = dur_seconds(row["dur"])
        entries.append({
            "date": day.strftime("%Y-%m-%d"),
            "start": start.strftime("%Y-%m-%dT%H:%M:%S"),
            "end": (start + timedelta(seconds=secs)).strftime("%Y-%m-%dT%H:%M:%S"),
            "duration_seconds": secs,
            "duration_minutes": round(secs / 60, 2),
            "description": " ".join(x for x in (pre, row["desc"], date["post"]) if x.strip()).strip(),
            "project": "" if project == "-" else project,
            "tags": "" if tags == "-" else tags,
        })
        i += 3
    return entries


def pdf_to_csv(src: str, out: str) -> int:
    entries = parse(src)
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(entries[0].keys()))
        w.writeheader()
        w.writerows(entries)
    total = sum(e["duration_seconds"] for e in entries)
    h, rem = divmod(total, 3600)
    print(f"entries: {len(entries)}")
    print(f"total: {h}:{rem // 60:02d}:{rem % 60:02d}")
    print(f"range: {min(e['date'] for e in entries)} .. {max(e['date'] for e in entries)}")
    print("descriptions:", Counter(e["description"] for e in entries).most_common(10))
    print("projects:", Counter(e["project"] for e in entries).most_common(10))
    print("tags:", Counter(e["tags"] for e in entries).most_common(5))
    return 0


# --- CSV -> bonsai -------------------------------------------------------------

TOGGL_PROJECTS = {"Working": "work", "Learning": "learning", "Tinkering": "tinkering"}


def toggl_tag(project: str) -> str | None:
    """bonsai tag for a Toggl row, or None (no project, or one we don't know) to set it aside."""
    return TOGGL_PROJECTS.get(project)


def set_aside_path(src: Path) -> Path:
    """New file next to the input, stamped with the time; never an existing one."""
    base = f"{src.stem}-set-aside-{datetime.now():%Y%m%d-%H%M%S}"
    target, n = src.with_name(f"{base}.csv"), 1
    while target.exists():
        n += 1
        target = src.with_name(f"{base}-{n}.csv")
    return target


def run(conn, file: str, dry_run: bool) -> int:
    with open(file, newline="") as f:
        csv_rows = list(csv.DictReader(f))
    # Compare local clock time ("2026-01-05T07:30:00"), so the check doesn't depend on the timezone.
    taken = {r[0][:19] for r in conn.execute("SELECT start FROM sessions")}
    new, zero, dup, aside = [], 0, 0, []
    for r in csv_rows:
        minutes = round(float(r["duration_minutes"]))
        if minutes < 1:
            zero += 1
            continue
        tag = toggl_tag(r["project"])
        if tag is None:
            aside.append(r)
            continue
        start = datetime.fromisoformat(r["start"])
        clock = start.isoformat(timespec="seconds")
        if clock in taken:
            dup += 1
            continue
        taken.add(clock)
        start = start.astimezone()
        end = datetime.fromisoformat(r["end"]).astimezone()
        new.append((tag, start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds"),
                    minutes, float(minutes), 1, "toggl"))

    print(f"Read {len(csv_rows)} rows from {Path(file).name}")
    print(f"Skipped: {zero} zero-length, {dup} already imported, {len(aside)} set aside (no or unknown project)")
    unknown: dict[str, int] = {}
    for r in aside:
        if r["project"]:
            unknown[r["project"]] = unknown.get(r["project"], 0) + 1
    if unknown:
        print("Unknown projects: " + ", ".join(f"{p} ({n})" for p, n in sorted(unknown.items())))
    if new:
        days = sorted(n[1][:10] for n in new)
        by_tag: dict[str, float] = {}
        for n in new:
            by_tag[n[0]] = by_tag.get(n[0], 0) + n[3] / 60
        print(f"To add: {len(new)} sessions, {days[0]} to {days[-1]}")
        print(f"Hours: {sum(by_tag.values()):,.1f} total · "
              + " · ".join(f"{t} {h:,.1f}" for t, h in sorted(by_tag.items(), key=lambda kv: -kv[1])))
    else:
        print("To add: 0 sessions")
    if dry_run:
        print("Dry run: nothing saved.")
        return 0

    with conn:  # one transaction: all rows or none
        tags = bonsai.get_tags(conn)
        for tag in sorted({n[0] for n in new} - {"work"} - set(tags)):
            emoji = bonsai.next_default_emoji(list(tags.values()))
            conn.execute("INSERT INTO tags (name, emoji) VALUES (?, ?)", (tag, emoji))
            tags[tag] = emoji
        conn.executemany(
            "INSERT INTO sessions (tag, start, end, planned_min, actual_min, completed, source)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)", new)
    print(f"Imported {len(new)} sessions.")
    if aside:
        src = Path(file)
        target = set_aside_path(src)
        with target.open("x", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(csv_rows[0]))
            writer.writeheader()
            writer.writerows(aside)
        print(f"Wrote {len(aside)} set-aside rows to {target}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="One-time backfill of Toggl history into bonsai.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pdf", help='convert a Toggl "Detailed report" PDF to CSV')
    p.add_argument("src")
    p.add_argument("out")
    p = sub.add_parser("import", help="import a Toggl CSV into bonsai")
    p.add_argument("file")
    p.add_argument("--dry-run", action="store_true", help="show what would be added, save nothing")
    args = parser.parse_args(argv)
    if args.cmd == "pdf":
        return pdf_to_csv(args.src, args.out)
    conn = bonsai.init_db(bonsai.db_path())
    try:
        return run(conn, args.file, args.dry_run)
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
