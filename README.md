# Chess AI

A chess GUI and toolkit for a course assignment: implement **alpha-beta
pruning** and **Monte Carlo Tree Search (MCTS)**, then **compare** them.

The team writes the two engines. This repository provides everything around
them: a playable GUI that shows what an engine is thinking, the engine
plug-in interface, two weak baseline engines, and match, puzzle and
benchmark tools that produce the comparison data (a report template comes
later). Chess rules come from
[`python-chess`](https://python-chess.readthedocs.io/).

## Install

Python 3.11 or newer with tkinter.

```bash
uv sync                 # creates .venv with python-chess
```

Without uv: `python -m pip install chess`, then drop the `uv run` prefix
below. (On Windows use `py` instead of `python`.)

## Play

```bash
uv run python -m chessai                                  # you (White) vs greedy (Black)
uv run python -m chessai --white greedy --black random    # watch two engines
uv run python -m chessai --black greedy --time 0.5        # engine thinks 0.5 s per move
uv run python -m chessai --fen "8/P6k/8/8/8/8/8/K7 w - - 0 1"
uv run python -m chessai --seed 7 --letters               # reproducible engines, letter pieces
```

| Option | Meaning | Default |
|---|---|---|
| `--white`, `--black` | `human` or an engine name (`random`, `greedy`, …) | `human`, `greedy` |
| `--time` | engine seconds per move | `1.0` |
| `--fen` | start position | standard start |
| `--seed` | seed for the engines' randomness (same seed → same game) | `0` |
| `--letters` | draw pieces as letters K Q R B N P / k q r b n p | off |

### Controls

| Action | Mouse / key |
|---|---|
| Move | click a piece, then a highlighted square (a picker appears for promotions) |
| New game | **New game** / `F2` |
| Undo / Redo | **Undo** / **Redo**, `Ctrl+Z` / `Ctrl+Y` (`⌘Z` / `⌘Y` on macOS) |
| Flip the board | **Flip** / `F` |
| Ask an engine for a hint | **Hint** / `H` (uses the *Hint engine* selector) |
| Make a thinking engine move now | **Stop** |
| Pause / resume engine play | **Pause** / **Resume** / `Space` |
| Show or hide the analysis | **Show analysis** / `A` |
| Cancel a selection | `Esc` |
| Start from an opening | pick it under **Opening**, then **New game** |
| Load a position | **From FEN…** |
| Copy the game / position | **Copy PGN** / **Copy FEN** |

White and Black can each be a human or any engine, and you can switch them
mid-game. Typing in the *Seconds / move* box never triggers shortcuts. Undo, Redo and *From FEN* pause engine play so an engine does not
instantly replay the move you took back; press `Space` to continue.

### What the analysis view shows

After an engine searches (for a move or a hint), the *Analysis* box and the
blue arrows on the board show what it reported:

- **Alpha-beta style:** `depth`, `nodes`, nodes per second, `score` (in
  pawns, **from White's point of view**: +1.20 means White is ahead), and the
  principal variation (`PV: e4 e5 Nf3`).
- **MCTS style:** simulations (`nodes`) and the top candidate moves with
  their visit counts, share of visits and win rate.
- **Arrows:** the top three candidates (or the first PV move), thickest =
  best. Arrows are shown while that position is still on the board.

Engines decide what they report; see
[`docs/engine-interface.md`](docs/engine-interface.md).

## Engines

| Name | What it does |
|---|---|
| `random` | Plays a random legal move. |
| `greedy` | Looks one move ahead: mates if it can, otherwise grabs the most material. |
| `minimax`, `alphabeta`, `mcts` | Written by the team in `chessai/engines/`: see **Writing the engines** below. Until written they report an engine error. |

To add an engine, implement the interface in
[`docs/engine-interface.md`](docs/engine-interface.md) and register it in
`chessai/engines/__init__.py`. It then appears in the GUI's dropdowns and
`--white/--black`.

## Writing the engines

`chessai/engines/evaluate.py`, `alphabeta.py` and `mcts.py` are stubs: every
function has its exact signature and description, and raises
`NotImplementedError` until you write it. Follow the tutorials in
[`docs/learn/`](docs/learn/README.md): minimax, evaluation, alpha-beta, a
strong alpha-beta engine, MCTS, MCTS for chess, and running a fair
comparison. Each one ends with a step test:

```bash
uv run pytest tests/learn -v      # unwritten steps are skipped and name the tutorial to read
```

## Comparison tools

```bash
uv run python -m chessai.match --engines alphabeta mcts --time 0.1,0.5,1 --out results/h2h
uv run python -m chessai.puzzles --engine mcts --time 1 --out results/puzzles-mcts
uv run python -m chessai.bench --engine alphabeta --depth 4 --out results/bench-ab
```

- **`match`**: engines play each other from 50 bundled openings, each opening
  once with each colour, and the tool reports score, Elo difference and a 95%
  confidence range.
- **`puzzles`**: solve rate on 300 Lichess puzzles (mate in 1/2/3, winning
  material).
- **`bench`**: nodes, depth and speed per position.

Every option, output column and recommended run for the report is explained
in [`docs/tools.md`](docs/tools.md). Results go to `results/` (git-ignored).

## Project layout

```
chessai/
  engines/base.py        engine contract: SearchLimit, SearchInfo, SearchResult, run_search
  engines/baselines.py   random and greedy engines
  engines/evaluate.py    shared evaluation (team; stub)
  engines/alphabeta.py   minimax and alpha-beta (team; stub)
  engines/mcts.py        Monte Carlo Tree Search (team; stub)
  engines/__init__.py    ENGINES registry
  session.py             one game: moves, undo/redo, result, PGN
  gui/                   tkinter app; searches run on a background thread
  data.py                loads the bundled openings and puzzles
  match/                 match tool: one game, the schedule, the CLI
  puzzles.py, bench.py   puzzle and benchmark tools
  stats.py, output.py    Elo and confidence ranges; results folders and manifest
  workers.py             runs each game/puzzle in its own process (survives hung or crashing engines)
data/                    openings.txt, puzzles.csv (Lichess, CC0); see data/README.md
scripts/build_puzzles.py rebuilds data/puzzles.csv from the Lichess database
docs/
  engine-interface.md    how to write and plug in an engine
  tools.md               the comparison tools in detail
  learn/                 tutorials 1–7 for writing the engines
  superpowers/           design and plans
tests/                   tests of the toolkit; tests/learn/ = the step tests for your engines
```

## Platform notes

Works on Linux, Windows and macOS.

- **Windows:** the python.org installer includes tkinter; use `py -m chessai`
  if `python` is not on PATH.
- **macOS:** the python.org installer includes tkinter; with Homebrew Python,
  `brew install python-tk`.
- **Linux:** install your distro's tk package if `import tkinter` fails
  (`sudo apt install python3-tk`, `sudo pacman -S tk`).
- **Piece symbols:** the GUI looks for a font with chess symbols (Segoe UI
  Symbol, Apple Symbols, DejaVu Sans, Noto Sans Symbols 2, FreeSerif, …). If
  none is installed it switches to letters automatically; you can also
  toggle **Letter pieces**.

## Development

```bash
uv run pytest
```

Note for Linux (X11): text copied with **Copy PGN / Copy FEN** is lost when
the app closes (a Tk limitation); paste it before quitting.

GUI tests open a hidden window and are skipped when no display is available.
