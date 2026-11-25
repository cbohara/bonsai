# BACKFILL — import 2026 Toggl history into bonsai

One-time import of my 2026 Toggl Track entries into bonsai's database, so `bon week`, the garden and my year-end hours analysis cover all of 2026.

## Input

`toggl-2026-merged.csv` (both Toggl orgs merged, no overlaps; 9 start-stops of a few seconds are still in it). Columns:

| column | example |
|---|---|
| `date` | `2026-01-05` |
| `start` | `2026-01-05T07:30:00` (local time, no offset) |
| `end` | `2026-01-05T08:00:00` |
| `duration_seconds` | `1800` |
| `duration_minutes` | `30.0` |
| `description` | `work`, `jira ticket`, `deep learning ai`, … |
| `project` | `Working`, `Learning`, `Tinkering`, or empty |
| `tags` | always empty (lost in Toggl) |

## Command

`uv run backfill.py import <file.csv> [--dry-run]`

`backfill.py` is a one-time script next to `bonsai.py`, not part of the app. It also has `uv run backfill.py pdf <report.pdf> <out.csv>`, which turns a Toggl "Detailed report" PDF into this CSV format (no merging or cleaning).

## Rules

- One bonsai session per CSV row:
  - `start`, `end` from the CSV, stored in bonsai's usual local-time format
  - `planned_min = actual_min = round(duration_minutes)`
  - `completed = 1`, `source = 'toggl'`
- Tag by project:
  - `Working` → `work`
  - `Learning` → `learning`
  - `Tinkering` → `tinkering`
  - empty or any other project → set the row aside; the rest still import. Output lists each unknown project with its row count.
- Set-aside rows go to a new `<input>-set-aside-<timestamp>.csv` next to the input (never overwrites an earlier one), same columns, for me to fix by hand. Importing that file after I fill in projects adds only those rows.
- Skip rows that round to 0 minutes (zero-length or a few seconds).
- Skip a row if a session with the same local `start` clock time already exists (offset ignored), so running the import twice adds nothing.
- Life tags created by the import (`learning`, `tinkering`) get their default emoji and don't trigger the "New tag?" prompt.
- Save everything in one transaction: either all rows import or none do.

## Output

Both modes print: rows read, rows skipped (zero-length, already imported, set aside), sessions to add, date range, and hours per tag. `--dry-run` stops there and saves nothing, including the set-aside file.

Expected for `toggl-2026-merged.csv` on an empty DB:

- 723 rows read: 10 zero-length, 22 set aside (all no-project, 2026-11-13 to 2026-11-25)
- 691 sessions, 2026-01-05 to 2026-11-12
- 1,395.8 h total: work 1,315.6 h, tinkering 40.3 h, learning 39.9 h

## Acceptance tests

1. `--dry-run` prints exactly the expected numbers above and leaves the database unchanged.
2. A real import adds 691 sessions and writes 22 rows to the set-aside file; `bon week --last` and `bon garden` show the imported days.
3. Running the import a second time adds 0 sessions.
4. A CSV with an unknown project (e.g. `Side gig`) imports the other rows, sets that one aside, and names the project.
5. pytest unit tests for the project-to-tag mapping and the duplicate check.

## Not in scope

- Importing other years or other Toggl export formats (PDF, JSON, API)
- Any ongoing sync with Toggl
- Detecting overlap with existing bonsai sessions beyond the exact-start check (I'll check `bon week` myself)
