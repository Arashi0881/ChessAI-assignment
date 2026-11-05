# Data files

## `openings.txt`

50 well-known opening lines (4–10 plies each), written for this project. A
match plays each opening twice, once with each engine as White, so the two
engines face the same positions. Format: `Name | moves in SAN`; `#` starts a
comment. Edit freely: the tests check that every line is legal and that no
two openings reach the same position.

## `puzzles.csv`

300 puzzles from the [Lichess puzzle database](https://database.lichess.org/#puzzles),
which Lichess releases under **CC0** (public domain). Each row keeps its
Lichess id and a link to the puzzle on lichess.org.

| Column | Meaning |
|---|---|
| `puzzle_id` | Lichess puzzle id |
| `category` | `mate1`, `mate2`, `mate3` (mate in 1/2/3) or `material` (wins material or a decisive advantage in 1–3 moves, no mate) |
| `fen` | the position *before* the opponent's move |
| `moves` | UCI moves: the first is the opponent's move that sets up the puzzle, then the solver's and the opponent's replies alternate |
| `rating` | Lichess puzzle rating (difficulty) |
| `themes` | Lichess theme tags |
| `url` | the puzzle on lichess.org |

Sample: 75 per category, drawn uniformly (reservoir sampling, seed 0) from
puzzles with rating deviation < 100, popularity ≥ 80 and at least 500
plays, then sorted by category and rating.

Built from the database file dated 2026-11-01 with:

```bash
uv run --group data python scripts/build_puzzles.py
```

The script streams the ~310 MB compressed file once and stores nothing but
the sample. Options: `--source` (URL or a local `.zst`), `--per-category`,
`--seed`, `--out`. A newer database file gives a different sample.
