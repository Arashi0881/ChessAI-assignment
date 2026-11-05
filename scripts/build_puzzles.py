"""Build data/puzzles.csv: a seeded sample of the Lichess puzzle database (CC0).

    uv run --group data python scripts/build_puzzles.py

Streams the compressed database (about 310 MB) once and never stores it.
Keeps well-tested puzzles only, in four categories of equal size.
"""
from __future__ import annotations

import argparse
import csv
import io
import random
import sys
import urllib.request
from pathlib import Path

import zstandard

SOURCE = "https://database.lichess.org/lichess_db_puzzle.csv.zst"
OUT = Path(__file__).resolve().parent.parent / "data" / "puzzles.csv"
COLUMNS = ["puzzle_id", "category", "fen", "moves", "rating", "themes", "url"]
CATEGORIES = ("mate1", "mate2", "mate3", "material")
MATE_THEMES = {"mateIn1": "mate1", "mateIn2": "mate2", "mateIn3": "mate3"}

# Quality filters: a stable rating, liked by players, and played often.
MAX_RATING_DEVIATION = 100
MIN_POPULARITY = 80
MIN_PLAYS = 500


def category(row: dict) -> str | None:
    themes = set(row["Themes"].split())
    plies = len(row["Moves"].split())
    for theme, name in MATE_THEMES.items():
        if theme in themes:
            return name if plies == 2 * int(name[-1]) else None
    if themes & {"advantage", "crushing"} and not any("mate" in t.lower() for t in themes):
        return "material" if plies in (2, 4, 6) else None
    return None


def good(row: dict) -> bool:
    return (int(row["RatingDeviation"]) < MAX_RATING_DEVIATION
            and int(row["Popularity"]) >= MIN_POPULARITY
            and int(row["NbPlays"]) >= MIN_PLAYS)


def open_source(source: str):
    if source.startswith(("http://", "https://")):
        return urllib.request.urlopen(source)
    return open(source, "rb")


def sample(rows, per_category: int, rng: random.Random) -> dict[str, list[dict]]:
    """Reservoir sampling: a uniform sample of each category in one pass."""
    kept = {name: [] for name in CATEGORIES}
    seen = dict.fromkeys(CATEGORIES, 0)
    for row in rows:
        name = category(row)
        if name is None or not good(row):
            continue
        seen[name] += 1
        if len(kept[name]) < per_category:
            kept[name].append(row)
        else:
            slot = rng.randrange(seen[name])
            if slot < per_category:
                kept[name][slot] = row
    for name in CATEGORIES:
        print(f"{name}: {seen[name]:,} eligible, kept {len(kept[name])}", file=sys.stderr)
    return kept


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", default=SOURCE, help="URL or local path of lichess_db_puzzle.csv.zst")
    parser.add_argument("--per-category", type=int, default=75)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args(argv)

    with open_source(args.source) as raw:
        text = io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(raw), encoding="utf-8")
        kept = sample(csv.DictReader(text), args.per_category, random.Random(f"puzzles:{args.seed}"))

    rows = []
    for name, picked in kept.items():
        if len(picked) < args.per_category:
            parser.error(f"only {len(picked)} {name} puzzles pass the filters")
        for row in picked:
            rows.append({
                "puzzle_id": row["PuzzleId"], "category": name, "fen": row["FEN"],
                "moves": row["Moves"], "rating": int(row["Rating"]), "themes": row["Themes"],
                "url": f"https://lichess.org/training/{row['PuzzleId']}",
            })
    rows.sort(key=lambda r: (r["category"], r["rating"], r["puzzle_id"]))
    with args.out.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} puzzles to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
