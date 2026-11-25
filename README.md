# bonsai 🌱

A focus timer for my Mac's terminal. It dings in my headphones when time's up and grows a garden from the sessions I finish.

I built it because I kept missing the end-of-session alert in other timers. I liked the idea behind Forest, growing something while you focus, but it was buggy and it lives on my phone, which is the thing I'm trying not to pick up. So I wanted the same idea in my terminal, plus one place to see whether my work hours were creeping past 40 a week.

```
╭──────────────────── bonsai ────────────────────╮
│                                                │
│    work                                        │
│                                                │
│     ▀█ █▀▀   ▀▀█  ▀█                           │
│      █ █▀█ ▀  ▀█   █                           │
│      ▀ ▀▀▀ ▀ ▀▀▀   ▀                           │
│                                                │
│    ━━━━━━━━━━━━━━━━━╸                          │
│    🌱 🌱 · ·                                   │
│                                                │
╰────────────────── q to stop ───────────────────╯
```

## Setup

Needs macOS and [uv](https://docs.astral.sh/uv/). Add to `~/.zshrc`:

```sh
alias bonsai="uv run ~/git/bonsai/bonsai.py"
alias bon=bonsai
```

Check the sound: `bon test-ding`

## A session

```mermaid
flowchart LR
    A["bon start w 30"] --> B["🌱 · · ·<br/>🌱 🌱 · ·<br/>🌱 🌱 🌱 ·"]
    B -- "q" --> C["🥀 hours only"]
    B -- "time's up" --> D["ding ×3<br/>Good focus session? [Y/n]"]
    D -- "y" --> E["🌵 planted"]
    D -- "n" --> C
```

```sh
bon start w 30         # work
bon start writing 45   # life tags are typed in full
bon                    # repeat the last one
```

## My week

```
$ bon week
  Day              Work   Life
 ──────────────────────────────
  Mon 2026-11-23    2.5    0.5
  Tue 2026-11-24    2.5    1.0
  Wed 2026-11-25    2.5    0.5
  ...
  Total             7.5    2.0

Work 7.5h / 40h  ████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
```

The bar turns yellow at 32h and red at 38h.

## My garden

One plant per 30 minutes. Work is always 🌵, and each life tag has its own plant.

```
$ bon garden
Garden  streak 3  ·  best 3  ·  19 plants

  Mon 2026-11-23   🌵 🌵 🌵 🌵 🌵   🍄        3.0
  Tue 2026-11-24   🌵 🌵 🌵 🌵 🌵   🌻 🌻     3.5
  Wed 2026-11-25   🌵 🌵 🌵 🌵 🌵   🍄        3.0

🌵 work  🍄 learning  🌻 writing
```

## Everything else

```sh
bon today                  # today's sessions
bon tag writing 🌻         # pick a life tag's plant
bon log w 30 --at 14:00    # add one I forgot
bon undo                   # delete the last one
bon export                 # CSV of everything
```

Data lives in `~/.bonsai/bonsai.db`. Sound, repeats and volume are at the top of `bonsai.py`.

Tests: `uv run --with pytest --with rich pytest -q`
