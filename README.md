# bonsai 🌱

A focus timer for my Mac's terminal. It dings in my headphones, tracks where my time goes, and grows a garden from the sessions I finish.

![bonsai timer](docs/img/timer.svg)

## Setup

Needs macOS and [uv](https://docs.astral.sh/uv/). Add to `~/.zshrc`:

```sh
alias bonsai="uv run ~/git/bonsai/bonsai.py"
```

Check the sound: `bonsai test-ding`

## A session

```mermaid
flowchart LR
    A["🌱 🌱 · ·"] -- "time's up" --> B["ding<br/>focused?"]
    A -- "q" --> C["🥀 hours only"]
    B -- "y" --> D["🌵 planted"]
    B -- "n" --> C
```

```sh
bonsai start w 30         # work
bonsai start writing 45   # life tags are typed in full
bonsai                    # repeat the last one
```

## My week

```
$ bonsai week
  Day              Work   Life
 ──────────────────────────────
  Mon 2026-11-23    2.5    0.5
  Tue 2026-11-24    2.5    1.0
  Wed 2026-11-25    2.5    0.5
  ...
  Total             7.5    2.0

Work 7.5h / 40h  ████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

The bar is green, then yellow at 32h and red at 38h.

## My garden

One plant per 30 minutes. Work is always 🌵, and each life tag has its own plant.

```
$ bonsai garden
Garden  streak 3  ·  best 3  ·  19 plants

  Mon 2026-11-23   🌵 🌵 🌵 🌵 🌵   🍄        3.0
  Tue 2026-11-24   🌵 🌵 🌵 🌵 🌵   🌻 🌻     3.5
  Wed 2026-11-25   🌵 🌵 🌵 🌵 🌵   🍄        3.0

🌵 work  🍄 study  🌻 tinker
```

## Everything else

```sh
bonsai today                  # today's sessions
bonsai tag writing 🌻         # pick a life tag's plant
bonsai log w 30 --at 14:00    # add one I forgot
bonsai log w --start 9:00 --end 11:30   # or give the times
bonsai undo                   # delete the last one
bonsai export                 # CSV of everything
```

Data lives in `~/.bonsai/bonsai.db`. Sound, repeats and volume are at the top of `bonsai.py`.

Tests: `uv run --with pytest --with rich pytest -q`
