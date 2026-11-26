# bonsai 🌱

A focus timer for my Mac's terminal. It dings in my headphones, tracks where my time goes, and grows a garden from the sessions I finish.

```
$ bonsai start work 30
```

![bonsai timer](docs/img/timer.svg?v=2)

```
$ bonsai garden
```

![bonsai garden](docs/img/garden.svg?v=3)

One plant per 30 minutes. Work is always 🌵, and each life tag has its own plant.

## Setup

Needs macOS and [uv](https://docs.astral.sh/uv/). Add to `~/.zshrc`:

```sh
alias bonsai="uv run ~/git/bonsai/bonsai.py"
```

Check the sound: `bonsai test-ding`

## A session

When the timer ends, it dings and asks if I really focused. Saying no, or stopping early with q, still logs the time, but nothing grows.

![bonsai focus check](docs/img/focus.svg?v=2)

```sh
bonsai start w 30         # work
bonsai start writing 45   # life tags are typed in full
bonsai                    # repeat the last one
```

## Everything else

```sh
bonsai today                  # today's sessions
bonsai week                   # hours this week
bonsai tag writing 🌻         # pick a life tag's plant
bonsai log w 30 --at 14:00    # add one I forgot
bonsai log w --start 9:00 --end 11:30   # or give the times
bonsai undo                   # delete the last one
bonsai export                 # CSV of everything
```

Data lives in `~/.bonsai/bonsai.db`. Sound, repeats and volume are at the top of `bonsai.py`.

Tests: `uv run --with pytest --with rich pytest -q`
