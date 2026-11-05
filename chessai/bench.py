"""python -m chessai.bench: search speed and size of one engine on fixed positions."""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
from pathlib import Path

import chess

from chessai.data import load_openings, load_puzzles
from chessai.engines import ENGINES
from chessai.engines.base import SearchLimit, engine_rng, run_search
from chessai.output import prepare_output_dir, write_manifest
from chessai.puzzles import parse_time

PUZZLES_PER_CATEGORY = 10
ROW_COLUMNS = ["position", "fen", "move", "nodes", "depth", "score_cp", "time_s", "nps", "problem"]
SUMMARY_COLUMNS = ["engine", "limit", "positions", "total_nodes", "total_time", "nps", "depth_mean", "problems"]


@dataclass(frozen=True)
class BenchRow:
    position: str
    fen: str
    move: str            # UCI, empty if the engine gave no playable move
    nodes: int
    depth: int | None
    score_cp: int | None
    time_s: float
    nps: float
    problem: str | None


def bench_positions(source: str) -> list[tuple[str, chess.Board]]:
    """"openings", "puzzles" (10 per category), or a file of `name | FEN` lines."""
    if source == "openings":
        return [(o.name, o.board()) for o in load_openings()]
    if source == "puzzles":
        taken: dict[str, int] = {}
        positions = []
        for p in load_puzzles():
            if taken.get(p.category, 0) < PUZZLES_PER_CATEGORY:
                taken[p.category] = taken.get(p.category, 0) + 1
                positions.append((p.puzzle_id, p.start_board()))
        return positions
    positions = []
    for number, raw in enumerate(Path(source).read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        name, sep, fen = (part.strip() for part in line.partition("|"))
        try:
            if not sep or not name:
                raise ValueError("expected 'name | FEN'")
            board = chess.Board(fen)
            if not board.is_valid() or board.is_game_over():
                raise ValueError("position is illegal or already over")
        except ValueError as exc:
            raise ValueError(f"{source} line {number}: {exc}") from None
        positions.append((name, board))
    return positions


def bench_position(engine, name: str, board: chess.Board, limit: SearchLimit) -> BenchRow:
    outcome = run_search(engine, board, limit)
    info = outcome.result.info if outcome.result else None
    nodes = info.nodes if info else 0
    return BenchRow(
        name, board.fen(), outcome.result.move.uci() if outcome.playable else "", nodes,
        info.depth if info else None, info.score_cp if info else None, outcome.elapsed,
        nodes / outcome.elapsed if outcome.elapsed > 0 else 0.0, outcome.problem,
    )


def positive_int(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError(f"must be at least 1, got {text!r}")
    return value


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m chessai.bench", description=__doc__.split(": ", 1)[1])
    parser.add_argument("--engine", required=True, help=f"one of: {', '.join(ENGINES)}")
    limits = parser.add_mutually_exclusive_group(required=True)
    limits.add_argument("--depth", type=positive_int, help="search to this depth (alpha-beta)")
    limits.add_argument("--iterations", type=positive_int, help="run this many simulations (MCTS)")
    limits.add_argument("--time", type=parse_time, help="seconds per position")
    parser.add_argument("--positions", default="openings", help="openings, puzzles, or a file of 'name | FEN' lines")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--force", action="store_true", help="overwrite results already in --out")
    args = parser.parse_args(argv)

    if args.engine not in ENGINES:
        parser.error(f"unknown engine {args.engine}; choose from {', '.join(ENGINES)}")
    limit = SearchLimit(time_s=args.time, depth=args.depth, iterations=args.iterations)
    try:
        positions = bench_positions(args.positions)
        out = prepare_output_dir(args.out, args.force)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))

    write_manifest(out, vars(args), {"positions_total": len(positions)})
    rows = []
    for i, (name, board) in enumerate(positions, 1):
        engine = ENGINES[args.engine](engine_rng(args.seed, f"{args.engine}:{name}"))
        row = bench_position(engine, name, board, limit)
        rows.append(row)
        print(f"[{i}/{len(positions)}] {name}: {row.move or '-'} nodes {row.nodes:,} "
              f"depth {row.depth if row.depth is not None else '-'} {row.time_s:.2f} s"
              + (f" — {row.problem}" if row.problem else ""), flush=True)

    with (out / "bench.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, ROW_COLUMNS)
        writer.writeheader()
        for row in rows:
            values = asdict(row)
            values.update(time_s=round(row.time_s, 4), nps=round(row.nps, 1),
                          depth="" if row.depth is None else row.depth,
                          score_cp="" if row.score_cp is None else row.score_cp, problem=row.problem or "")
            writer.writerow(values)

    total_nodes = sum(r.nodes for r in rows)
    total_time = sum(r.time_s for r in rows)
    depths = [r.depth for r in rows if r.depth is not None]
    limit_text = (f"depth {args.depth}" if args.depth else
                  f"iterations {args.iterations}" if args.iterations else f"time {args.time:g} s")
    summary = {
        "engine": args.engine, "limit": limit_text, "positions": len(rows), "total_nodes": total_nodes,
        "total_time": round(total_time, 3), "nps": round(total_nodes / total_time, 1) if total_time > 0 else 0,
        "depth_mean": round(sum(depths) / len(depths), 2) if depths else "",
        "problems": sum(r.problem is not None for r in rows),
    }
    with (out / "summary.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, SUMMARY_COLUMNS)
        writer.writeheader()
        writer.writerow(summary)
    print(f"\n{args.engine}, {limit_text}: {len(rows)} positions, {total_nodes:,} nodes in "
          f"{total_time:.2f} s ({summary['nps']:,} nodes/s), mean depth {summary['depth_mean'] or '-'}; "
          f"results in {out}")


if __name__ == "__main__":
    main()
