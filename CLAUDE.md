# bonsai

Single-file Python CLI (`bonsai.py`), macOS only. Spec: `bonsai-SPEC.md`.

## Commands
- Test: `uv run --with pytest --with rich pytest -q`
- Lint: `uvx ruff check .`

## Conventions
- Everything lives in `bonsai.py`. Dependencies are declared in its PEP 723 header (`rich` only). No `pyproject.toml`.
- Tests in `tests/`, import `bonsai` from the repo root. Keep pure logic (streak, week bucketing, plant stages, plants-per-session) in plain functions so it tests without a terminal, sound, or real DB.
- Tests must not play sounds, show notifications, run `caffeinate`, or touch `~/.bonsai/`. Use a temp DB path.

## Baton
- Approval mode: yolo
- Ship mode: merge
- Test styles: example-based only
