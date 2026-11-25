# bonsai

Single-file Python CLI (`bonsai.py`), macOS only. Spec: `docs/SPEC.md`.

## Commands
- Test: `uv run --with pytest --with rich pytest -q`
- Lint: `uvx ruff check .`

## Conventions
- Everything lives in `bonsai.py`. Dependencies are declared in its PEP 723 header (`rich` only). No `pyproject.toml`.
- Exception: `backfill.py` is a one-time Toggl import (`docs/BACKFILL.md`), not part of the app. It imports `bonsai`; `pdfplumber` is imported only inside its `pdf` command so tests don't need it.
- Tests in `tests/`, import `bonsai` from the repo root. Keep pure logic (streak, week bucketing, plant stages, plants-per-session) in plain functions so it tests without a terminal, sound, or real DB.
- Tests must not play sounds, show notifications, run `caffeinate`, or touch `~/.bonsai/`. Use a temp DB path.

## Baton
- Approval mode: yolo
- Ship mode: merge
- Test styles: example-based only
