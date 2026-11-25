# bonsai 🌱

A Pomodoro timer and time tracker for my Mac's terminal. I start a focus session, get a ding in my headphones when it ends, and grow a small garden for every session I finish.

I built it because I kept missing the end-of-session alert in other timers. I liked the idea behind Forest, growing something while you focus, but it was buggy and it lives on my phone, which is the thing I'm trying not to pick up. So I wanted the same idea in my terminal, plus one place to see whether my work hours were creeping past 40 a week.

## Setup

You need macOS and [uv](https://docs.astral.sh/uv/). The first run installs the one dependency (`rich`).

Clone the repo, then add this to `~/.zshrc`:

```sh
alias bonsai="uv run ~/git/bonsai/bonsai.py"
alias bon=bonsai
```

Then check the sound with `bon test-ding`.

## A normal day

```sh
bon start w 30        # 30-minute work session
bon                   # same tag and length as last time
bon start writing 45  # a life tag, typed in full
```

During a session, press `q` to stop early. You keep the hours, but no plant grows.

When the timer ends, the ding plays three times and asks **Good focus session? [Y/n]**. Answer with one key while it's still playing. `n` keeps the hours but skips the plant, for the times I sat there and didn't really focus.

## Checking in

```sh
bon today    # today's sessions and garden
bon week     # hours per day, work vs life, and a bar toward 40h
bon garden   # the last 4 weeks of plants and my streak
```

## Tags

Every session is either **work** (🌵) or a **life** tag like learning or writing. Each life tag gets its own plant. I can change it:

```sh
bon tag              # list tags
bon tag writing 🌻   # set writing's plant
```

## Fixing mistakes

```sh
bon log w 30 --at 14:00   # add a session I forgot to start
bon undo                  # delete the last session
bon export                # all sessions as a CSV
```

## Where the data lives

Everything is in `~/.bonsai/bonsai.db`, a SQLite file outside the repo. Delete it to start over.

## Changing the sound

The sound file, repeat count and volume are constants at the top of `bonsai.py`.

## Tests

```sh
uv run --with pytest --with rich pytest -q
```
