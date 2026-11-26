# SPEC — `bonsai`: terminal Pomodoro + time tracker with a garden

A single-file Python CLI for my personal Mac. Start a focus session tagged **work** or a **life** tag like **study**, get a reliable ding in my headphones when it ends, track weekly hours (keep work under 40h), and grow a small garden as a reward for finished sessions.

## Success condition (v1 is done when…)

I run every focus session for a week with `bonsai`, never miss the end-of-session ding, and `bonsai week` tells me my work and life hours.

## Platform & stack

- macOS only. Python 3.12+. A single file, `bonsai.py`, with PEP 723 inline script metadata declaring its one dependency (`# /// script` … `dependencies = ["rich"]` … `# ///`), so `uv run bonsai.py` installs `rich` automatically. No `pyproject.toml`, no `uv tool install`.
- Run it through two aliases in `~/.zshrc`: `alias bonsai="uv run ~/git/bonsai/bonsai.py"` and `alias bon=bonsai`. All examples work with either name.
- One dependency: `rich` (countdown, colors, tables). Everything else stdlib (`sqlite3`, `subprocess`, `argparse`, `csv`).
- Data: `~/.bonsai/bonsai.db` (SQLite). Create on first run.

## Commands

| Command | What it does |
|---|---|
| `bonsai start [tag] [minutes]` | Start a session. Tag defaults to `work`, minutes to `30` (both remembered from last use). Accepts `w` as a shortcut for work. Life tags are always typed in full. |
| `bonsai` | Alias for `bonsai start` with last-used tag and minutes. |
| `bonsai today` | Today's sessions, total per tag, today's garden row. |
| `bonsai week [--last] [--detail]` | This week (Mon–Sun): hours per day in two top-level columns, **work** and **life**, plus the work total vs 40h. `--detail` breaks life down by tag (study, writing, …). |
| `bonsai garden` | Last 4 weeks as a garden grid + current streak. |
| `bonsai log <tag> <minutes> [--date YYYY-MM-DD] [--at HH:MM]`<br>`bonsai log <tag> --start HH:MM --end HH:MM [--date YYYY-MM-DD]` | Manually add a session I forgot to track (counts toward hours; plants as usual). Saved with `completed = 1`, `source = 'manual'`. `--start` is the same as `--at`. With `--end`, minutes are `end - start`; giving minutes too, `--end` without `--start`, or `end <= start` is a usage error (exit 2). Same-day only. If the range overlaps a saved session (ends touching don't count), ask `Overlaps 🌵 work 09:00–10:00. Log anyway? [y/N]`; no saves nothing. |
| `bonsai tag [name] [emoji]` | No args: list tags with their emoji and group. `bonsai tag writing 🌻` sets a life tag's plant (applies to past plants too, since it's looked up at display time). Refuses 🌵 and refuses changing `work`. |
| `bonsai undo` | Delete the most recent session (show it, ask y/n). |
| `bonsai export [file.csv]` | CSV of all sessions. Default `~/bonsai-export-YYYY-MM-DD.csv`. |

## Session behavior

- Full-screen-ish `rich` live view: tag, big countdown `MM:SS`, progress bar, and the growing plant (see Garden).
- Deadline computed from wall-clock start (`time.time()`), so a laptop that sleeps or lags still ends on time.
- **Keep the Mac awake** for the session: run `caffeinate -i -w <pid>` as a child process so it ends when `bonsai` exits. This only prevents idle sleep; closing the lid still sleeps the Mac. That's fine: the wall-clock deadline handles it (see test 3).
- `actual_min` is capped at `planned_min` (a session that ends late because the Mac slept still records the planned length).
- **New tag check:** the first time a tag is used (`start` or `log`), ask `New tag "stduy"? [y/N]` so typos don't become tags. `work`, `w` and existing tags never ask. `study` is an ordinary life tag and asks the first time like any other.
- **`q` or Esc = stop early** (Ctrl+C also works; Cmd+C can't, the terminal keeps it for copy). Record actual minutes (counts toward hours) with `completed = 0`. The plant wilts; nothing is planted. The live view shows `q to stop`.
- **Pause** is not a feature. Stop and start again.
- **Focus check:** when the timer ends, ask `Good focus session? [Y/n]` while the ding plays in the background. One keypress, no Enter: `y` or Enter keeps the plant. Answering skips any dings not yet started. `n` sets `completed = 0`: hours still count, no plant, no streak credit. The row is saved before the question, so Ctrl+C or closing the terminal keeps it as good. A "not focused" row is one with `completed = 0` and `actual_min = planned_min`.
- No break timer. After the focus check, print a one-line summary and exit.

## The ding (the most important part)

When the session ends:
1. Play `afplay /System/Library/Sounds/Glass.aiff` **3 times**, about 1.5 s apart. `afplay` uses the current output device, so connected headphones get it.
2. Show a macOS notification: `osascript -e 'display notification "Work session done — 30 min" with title "bonsai"'` (no `sound name`: the 3 afplay dings are the sound).
3. Print the terminal bell `\a` as a last fallback.
- Config is constants at the top of `bonsai.py` only: sound file path, repeat count, volume (`afplay -v 0.0–1.0`), default minutes. No config file in v1.
- `bonsai test-ding` plays the ding immediately, so I can check volume and headphones before starting.
- If `afplay` fails, don't crash: fall back to the notification and bell, and print a warning.

## Garden (gamification)

- **Work is always 🌵.** Every **life tag has its own plant emoji that I choose** (e.g. study 🍄, writing 🌻, reading 🌷). Emoji ignore terminal colors, so the plant itself carries the meaning. Hours text uses red/coral for work and green for life.
- A new life tag with no emoji gets the next unused one from a default list: 🍄 🌻 🌷 🌼 🌸 🍀 🌺 🪻. 🌵 is reserved for work and can't be chosen for a life tag.
- Within a day's row, life plants are grouped by tag (all 🍄 together, then 🌻, …) so it reads as patches, not noise.
- **One plant per full 30 minutes** of a completed session: 30 min → 1, 60 min → 2, 90 min → 3, 45 min → 1. A completed session shorter than 30 min still plants 1.
- Separate plants with one space (`🌵 🌵 🌵   🍄 🍄 🌻`), work first, then three spaces, then life.
- During a session a row of 4 spots fills in with progress: `🌱 · · ·` (0–24%) → `🌱 🌱 · ·` (25–49%) → `🌱 🌱 🌱 ·` (50–89%) → `🌱 🌱 🌱 🌵` (90–100%; the tag's own emoji for life). Stopping early wilts the newest sprout (e.g. `🌱 🌱 🥀 ·`), and nothing is planted.
- **Streak (simple, will likely change):** consecutive weekdays with at least one completed session. Weekends never break it; today doesn't break it until the day is over.
- `bonsai garden` shows a 4-week grid: one row per day (Mon–Sun) and its plants, no hours (those live in `week`). Header line: current streak, best streak, total plants. Below it: a legend built from the tags table (`🌵 work  🍄 study  🌻 writing …`).

## Tags and groups

- Every tag belongs to one of two groups: **work** (the tag `work`) or **life** (every other tag: `study`, `writing`, …). New tags join life automatically.
- All summaries lead with the two groups; per-tag detail is opt-in (`--detail`).

## Weekly hours & the 40h cap

- `bonsai week`: one row per day (Mon–Sun) with two hour columns, **work** and **life** (1 decimal), a totals row, and a work bar toward 40h. `--detail` adds one column per life tag. (Same layout as the Commands table describes.)
- Bar color: green under 32h, yellow 32–38h, red at 38h+.
- At the start of a work session, if this week's work total is already ≥ 38h, print a one-line heads-up (don't block).

## Data model

```sql
CREATE TABLE sessions (
  id            INTEGER PRIMARY KEY,
  tag           TEXT NOT NULL,          -- 'work', or any life tag ('study', ...)
  start         TEXT NOT NULL,          -- ISO 8601 local time with offset
  end           TEXT NOT NULL,
  planned_min   INTEGER NOT NULL,
  actual_min    REAL NOT NULL,
  completed     INTEGER NOT NULL,       -- 1 = ran to the ding and was focused, 0 = stopped early or not focused
  source        TEXT NOT NULL DEFAULT 'timer'  -- 'timer' | 'manual'
);
CREATE TABLE tags (name TEXT PRIMARY KEY, emoji TEXT NOT NULL);  -- life tags only; 'work' is always 🌵
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT);  -- last tag, last minutes
```

Write the session row when it ends (completed or stopped). If the process is killed mid-session, nothing is recorded. That's acceptable for v1.

## Non-goals (do NOT build)

- Web UI, localhost server, menu bar app, GUI of any kind
- Break timers, long-break cycles, auto-starting the next session
- Projects, clients, task lists
- Sync, cloud, accounts, Toggl integration
- Windows/Linux support
- Background daemon (the session runs in the foreground terminal)

## Acceptance tests

1. `bonsai start w 1` (1 min) → countdown runs, ding plays 3×, notification appears, row saved with `completed = 1`.
2. Start, then press `q` at 50% → row saved with `completed = 0`, actual minutes about half, nothing planted, terminal left clean. Ctrl+C does the same.
2b. Let a session finish, answer `n` to `Good focus session?` → row has `completed = 0`, `actual_min = planned_min`, nothing planted, hours count.
3. Close the laptop lid mid-session, reopen after the end time → ding plays right away on wake, `actual_min` = `planned_min` (capped).
4. `bonsai log study 30 --date <yesterday>` → shows in yesterday's row of `bonsai week` and `bonsai garden`.
5. Streak: sessions Thu, Fri, nothing on the weekend, Mon → streak 3.
6. `bonsai export` → CSV opens in a spreadsheet; row count and total hours match `bonsai week`.
7. `bonsai undo` removes only the last row after confirmation.
8. Running with no `~/.bonsai/` creates it and works on first try.
9. `bonsai tag writing 🌻` → past and future writing plants show 🌻; `bonsai tag writing 🌵` is refused; a brand-new tag gets the next unused default emoji.
10. `bonsai start learnign` asks to confirm the new tag; answering N exits without starting.
11. Unit tests (pytest) for streak math, week bucketing (Mon–Sun, local time), and plant-stage selection, and plants-per-session (30-min rule).

## Later (only after a week of real use)

- Milestone messages ("10th plant this week")

- `bonsai serve`: a read-only localhost page with a nicer illustrated garden, reading the same SQLite file
- Import my Toggl CSV export so past hours show in `bonsai week --last` and totals
