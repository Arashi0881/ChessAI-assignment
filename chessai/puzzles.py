"""python -m chessai.puzzles: how many bundled Lichess puzzles an engine solves."""
from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from pathlib import Path

from chessai.data import DATA_DIR, Puzzle, load_puzzles
from chessai.engines import ENGINES
from chessai.engines.base import SearchLimit, engine_rng
from chessai.match.game import guarded_search
from chessai.output import CsvAppender, prepare_output_dir, update_manifest, write_csv, write_manifest
from chessai.stats import wilson_interval
from chessai.workers import default_jobs, run_tasks

CATEGORIES = ("mate1", "mate2", "mate3", "material")
RESULT_COLUMNS = ["puzzle_id", "category", "rating", "solved", "failed_at", "played",
                  "expected", "time_total", "nodes", "problem", "url"]
SUMMARY_COLUMNS = ["category", "puzzles", "solved", "rate", "rate_low", "rate_high", "time_per_move"]


@dataclass(frozen=True)
class PuzzleResult:
    puzzle_id: str
    category: str
    rating: int
    solved: bool
    failed_at: int | None        # index of the solver move that went wrong
    played: tuple[str, ...]      # the engine's moves, UCI
    expected: tuple[str, ...]    # the solution's solver moves, UCI
    time_total: float
    nodes: int
    problem: str | None          # illegal move, error, overtime or no answer


def solve_puzzle(puzzle: Puzzle, engine, limit: SearchLimit, state=None) -> PuzzleResult:
    """Every solver move must match the solution, except that any mate counts on the last move.

    `state`, if given, gets the index of the move being searched in `state[1]`.
    """
    board = puzzle.start_board()
    expected = puzzle.solver_moves
    played: list[str] = []
    time_total, nodes, problem = 0.0, 0, None

    def result(solved: bool, failed_at: int | None) -> PuzzleResult:
        return PuzzleResult(puzzle.puzzle_id, puzzle.category, puzzle.rating, solved, failed_at,
                            tuple(played), tuple(m.uci() for m in expected), time_total, nodes, problem)

    for k, want in enumerate(expected):
        if state is not None:
            state[1] = k
        outcome = guarded_search(engine, board, limit)
        if outcome is None:
            problem = "no answer"
            return result(False, k)
        time_total += outcome.elapsed
        if not outcome.playable:
            problem = outcome.problem
            return result(False, k)
        if outcome.problem and problem is None:
            problem = outcome.problem          # overtime: the move still counts, but it is reported
        move = outcome.result.move
        nodes += outcome.result.info.nodes
        played.append(move.uci())
        board.push(move)
        last = k == len(expected) - 1
        if move != want and not (last and board.is_checkmate()):
            return result(False, k)
        if not last:
            board.push(puzzle.moves[2 * k + 2])   # the opponent's reply
    return result(True, None)


def _solve_task(task: tuple, state) -> PuzzleResult:
    puzzle, name, limit, seed = task
    try:
        engine = ENGINES[name](engine_rng(seed, f"{name}:{puzzle.puzzle_id}"))
    except Exception as exc:
        return PuzzleResult(puzzle.puzzle_id, puzzle.category, puzzle.rating, False, 0, (),
                            tuple(m.uci() for m in puzzle.solver_moves), 0.0, 0,
                            f"engine error: {type(exc).__name__}: {exc}")
    return solve_puzzle(puzzle, engine, limit, state)


def _crashed(task: tuple, marks: tuple[int, int]) -> PuzzleResult:
    puzzle = task[0]
    return PuzzleResult(puzzle.puzzle_id, puzzle.category, puzzle.rating, False, max(0, marks[1]), (),
                        tuple(m.uci() for m in puzzle.solver_moves), 0.0, 0,
                        "crash: the engine's process died")


def run_puzzles(puzzles: list[Puzzle], engine: str, limit: SearchLimit, seed: int, jobs: int,
                progress=None, engine_module: str | None = None) -> list[PuzzleResult]:
    """Solve every puzzle, each in a fresh process (see chessai.workers); results in puzzle order."""
    tasks = [(p, engine, limit, seed) for p in puzzles]
    return run_tasks(_solve_task, tasks, jobs, _crashed, progress, engine_module)


def parse_time(text: str) -> float:
    value = float(text)
    if not (math.isfinite(value) and value > 0):
        raise argparse.ArgumentTypeError(f"must be a positive number, got {text!r}")
    return value


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m chessai.puzzles", description=__doc__.split(": ", 1)[1])
    parser.add_argument("--engine", required=True, help=f"one of: {', '.join(ENGINES)}")
    parser.add_argument("--time", type=parse_time, default=1.0, help="seconds per move (default 1.0)")
    parser.add_argument("--category", default=",".join(CATEGORIES),
                        help=f"comma separated, from {','.join(CATEGORIES)} (default: all)")
    parser.add_argument("--limit", type=int, help="at most this many puzzles per category (easiest first)")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--jobs", type=int, default=default_jobs(),
                        help="puzzles solved in parallel, one process each (default: half the CPUs)")
    parser.add_argument("--puzzles", type=Path, default=DATA_DIR / "puzzles.csv")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--force", action="store_true", help="overwrite results already in --out")
    args = parser.parse_args(argv)

    if args.engine not in ENGINES:
        parser.error(f"unknown engine {args.engine}; choose from {', '.join(ENGINES)}")
    categories = [c.strip() for c in args.category.split(",") if c.strip()]
    bad = [c for c in categories if c not in CATEGORIES]
    if bad or not categories:
        parser.error(f"unknown category {', '.join(bad) or '(none)'}; choose from {', '.join(CATEGORIES)}")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")
    if args.jobs < 1:
        parser.error("--jobs must be at least 1")
    try:
        everything = load_puzzles(args.puzzles)
        out = prepare_output_dir(args.out, args.force)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    chosen = []
    for category in categories:
        chosen += [p for p in everything if p.category == category][: args.limit]

    write_manifest(out, vars(args), {"puzzles_total": len(chosen), "complete": False, "puzzles_done": 0})
    urls = {p.puzzle_id: p.url for p in chosen}
    results: list[PuzzleResult] = []
    rows_csv = CsvAppender(out / "puzzles.csv", RESULT_COLUMNS)

    def csv_row(r: PuzzleResult) -> dict:
        return {
            "puzzle_id": r.puzzle_id, "category": r.category, "rating": r.rating,
            "solved": int(r.solved), "failed_at": "" if r.failed_at is None else r.failed_at,
            "played": " ".join(r.played), "expected": " ".join(r.expected),
            "time_total": round(r.time_total, 4), "nodes": r.nodes, "problem": r.problem or "",
            "url": urls[r.puzzle_id],
        }

    def progress(r: PuzzleResult) -> None:
        results.append(r)
        rows_csv.append(csv_row(r))
        mark = "solved" if r.solved else f"failed at move {r.failed_at + 1}"
        print(f"[{len(results)}/{len(chosen)}] {r.category} {r.puzzle_id} ({r.rating}): {mark}"
              + (f" — {r.problem}" if r.problem else ""), flush=True)

    interrupted = False
    try:
        run_puzzles(chosen, args.engine, SearchLimit(time_s=args.time), args.seed, args.jobs, progress)
    except KeyboardInterrupt:
        interrupted = True
    finally:
        rows_csv.close()
    order = {p.puzzle_id: i for i, p in enumerate(chosen)}
    results.sort(key=lambda r: order[r.puzzle_id])
    write_csv(out / "puzzles.csv", [csv_row(r) for r in results], RESULT_COLUMNS)

    summary = []
    for category in [*categories, "all"]:
        group = [r for r in results if category in ("all", r.category)]
        solved = sum(r.solved for r in group)
        moves = sum(len(r.played) for r in group)
        low, high = wilson_interval(solved, len(group))
        summary.append({
            "category": category, "puzzles": len(group), "solved": solved,
            "rate": round(solved / len(group), 4) if group else "", "rate_low": round(low, 4),
            "rate_high": round(high, 4),
            "time_per_move": round(sum(r.time_total for r in group) / moves, 4) if moves else "",
        })
    write_csv(out / "summary.csv", summary, SUMMARY_COLUMNS)
    update_manifest(out, complete=not interrupted, puzzles_done=len(results))

    print(f"\n{args.engine} at {args.time:g} s/move; results in {out}")
    print(f"{'category':>9} {'solved':>11} {'rate':>6}  95% range")
    for row in summary:
        if row["puzzles"]:
            print(f"{row['category']:>9} {row['solved']:>5}/{row['puzzles']:<5} {row['rate']:>6.1%}  "
                  f"{row['rate_low']:.1%} – {row['rate_high']:.1%}")
    if interrupted:
        print(f"\nInterrupted: kept the {len(results)} finished puzzles of {len(chosen)}; "
              "manifest.json says complete: false. Re-run with --force to start over.")
        sys.exit(130)


if __name__ == "__main__":
    main()
