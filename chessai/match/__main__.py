"""python -m chessai.match: engine-vs-engine matches with Elo and confidence ranges."""
from __future__ import annotations

import argparse
import math
import sys
import time
from pathlib import Path

from chessai.data import DATA_DIR, load_openings
from chessai.engines import ENGINES
from chessai.match.game import GameRecord
from chessai.match.schedule import build_schedule, run_schedule, summarize
from chessai.output import CsvAppender, prepare_output_dir, update_manifest, write_csv, write_manifest
from chessai.stats import elo_from_score, elo_interval, format_elo, score
from chessai.workers import default_jobs

GAME_COLUMNS = ["index", "seed", "white", "black", "time_s", "opening", "white_eval", "black_eval",
                "result", "termination", "plies"]
SIDE_COLUMNS = ["moves", "time_mean", "time_max", "nodes", "nps", "depth_mean"]
SUMMARY_COLUMNS = ["a", "b", "time_s", "games", "wins", "draws", "losses", "score",
                   "elo", "elo_low", "elo_high", "forfeits_a", "forfeits_b"]


def parse_times(text: str) -> list[float]:
    try:
        times = [float(part) for part in text.split(",")]
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected numbers separated by commas, got {text!r}") from None
    if not all(math.isfinite(t) and t > 0 for t in times):
        raise argparse.ArgumentTypeError(f"times must be positive numbers, got {text!r}")
    return times


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m chessai.match", description=__doc__.split(": ", 1)[1])
    parser.add_argument("--engines", nargs="+", required=True, metavar="NAME",
                        help=f"two or more of: {', '.join(ENGINES)}; every pair plays")
    parser.add_argument("--time", type=parse_times, default=[0.1, 0.5, 1.0], metavar="S[,S…]",
                        help="seconds per move, comma separated (default 0.1,0.5,1)")
    parser.add_argument("--games", type=int, default=40, help="games per pair and time, even (default 40)")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--jobs", type=int, default=default_jobs(),
                        help="games played in parallel, one process each (default: half the CPUs)")
    parser.add_argument("--openings", type=Path, default=DATA_DIR / "openings.txt")
    parser.add_argument("--out", type=Path, required=True, help="folder for the results")
    parser.add_argument("--force", action="store_true", help="overwrite results already in --out")
    return parser


def game_row(r: GameRecord) -> dict:
    row = {c: getattr(r, c) for c in GAME_COLUMNS}
    for side, stats in (("white", r.white_stats), ("black", r.black_stats)):
        for c in SIDE_COLUMNS:
            value = getattr(stats, c)
            row[f"{side}_{c}"] = round(value, 4) if isinstance(value, float) else ("" if value is None else value)
    return row


def forfeits(records: list[GameRecord], engine: str, opponent: str, time_s: float) -> int:
    count = 0
    for r in records:
        if r.time_s == time_s and {r.white, r.black} == {engine, opponent} and r.termination.startswith("forfeit"):
            side = "white" if r.white == engine else "black"
            count += r.termination.endswith(f"({side})")
    return count


def summary_rows(records: list[GameRecord], engines: list[str], times: list[float]) -> list[dict]:
    rows = []
    for i, a in enumerate(engines):
        for b in engines[i + 1:]:
            for t in times:
                pair = summarize(records, a, b, t)
                if not pair.games:     # an interrupted run may not have reached this pair
                    continue
                low, high = elo_interval(pair)
                rows.append({
                    "a": a, "b": b, "time_s": t, "games": pair.games, "wins": pair.wins,
                    "draws": pair.draws, "losses": pair.losses, "score": round(score(pair), 4),
                    "elo": round(elo_from_score(score(pair)), 1), "elo_low": round(low, 1),
                    "elo_high": round(high, 1), "forfeits_a": forfeits(records, a, b, t),
                    "forfeits_b": forfeits(records, b, a, t),
                })
    return rows


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    unknown = [name for name in args.engines if name not in ENGINES]
    if unknown:
        parser.error(f"unknown engine(s) {', '.join(unknown)}; choose from {', '.join(ENGINES)}")
    if len(set(args.engines)) != len(args.engines) or len(args.engines) < 2:
        parser.error("--engines needs two or more different engines")
    if args.jobs < 1:
        parser.error("--jobs must be at least 1")
    try:
        specs = build_schedule(args.engines, args.time, args.games, load_openings(args.openings), args.seed)
        out = prepare_output_dir(args.out, args.force)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))

    write_manifest(out, vars(args), {"games_total": len(specs), "complete": False, "games_done": 0})
    columns = GAME_COLUMNS + [f"{side}_{c}" for side in ("white", "black") for c in SIDE_COLUMNS]
    started = time.perf_counter()
    records: list[GameRecord] = []
    games_csv = CsvAppender(out / "games.csv", columns)
    pgn_file = (out / "games.pgn").open("w", encoding="utf-8")

    def progress(r: GameRecord) -> None:
        records.append(r)
        games_csv.append(game_row(r))
        pgn_file.write(r.pgn + "\n\n")
        pgn_file.flush()
        print(f"[{len(records)}/{len(specs)}] game {r.index}: {r.white} vs {r.black} at {r.time_s:g} s: "
              f"{r.result} {r.termination} ({r.plies} plies)", flush=True)

    interrupted = False
    try:
        run_schedule(specs, args.jobs, progress)
    except KeyboardInterrupt:
        interrupted = True
    finally:
        games_csv.close()
        pgn_file.close()

    # rewrite in schedule order (games finish out of order when run in parallel)
    records.sort(key=lambda r: r.index)
    write_csv(out / "games.csv", [game_row(r) for r in records], columns)
    (out / "games.pgn").write_text("".join(r.pgn + "\n\n" for r in records), encoding="utf-8")
    summary = summary_rows(records, args.engines, args.time)
    write_csv(out / "summary.csv", summary, SUMMARY_COLUMNS)
    update_manifest(out, complete=not interrupted, games_done=len(records))

    print(f"\n{len(records)} games in {time.perf_counter() - started:.0f} s; results in {out}")
    print(f"{'A':>12} {'B':>12} {'s/move':>7} {'+':>4} {'=':>4} {'-':>4} {'score':>6}  Elo of A (95% range)")
    for row in summary:
        print(f"{row['a']:>12} {row['b']:>12} {row['time_s']:>7g} {row['wins']:>4} {row['draws']:>4} "
              f"{row['losses']:>4} {row['score']:>6.1%}  {format_elo(row['elo'])} "
              f"({format_elo(row['elo_low'])} to {format_elo(row['elo_high'])})")
    if interrupted:
        print(f"\nInterrupted: kept the {len(records)} finished games of {len(specs)}; "
              "manifest.json says complete: false. Re-run with --force to start over.")
        sys.exit(130)


if __name__ == "__main__":
    main()
