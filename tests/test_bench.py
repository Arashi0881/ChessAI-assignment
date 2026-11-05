import csv

import chess
import pytest

from chessai.bench import bench_position, bench_positions, main
from chessai.engines import GreedyEngine
from chessai.engines.base import SearchLimit, engine_rng


def test_positions_from_openings_and_puzzles():
    assert len(bench_positions("openings")) == 50
    puzzles = bench_positions("puzzles")
    assert len(puzzles) == 40
    assert all(isinstance(board, chess.Board) for _, board in puzzles)


def test_positions_from_file(tmp_path):
    path = tmp_path / "pos.txt"
    path.write_text("# mine\nStart | rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1\n\n"
                    "Rook end | 8/8/8/4k3/8/8/4K3/R7 w - - 0 1\n")
    names = [name for name, _ in bench_positions(str(path))]
    assert names == ["Start", "Rook end"]
    path.write_text("Broken | not a fen\n")
    with pytest.raises(ValueError, match="line 1"):
        bench_positions(str(path))


def test_bench_position():
    board = chess.Board()
    row = bench_position(GreedyEngine(engine_rng(0, "g")), "Start", board, SearchLimit(depth=1))
    assert row.nodes > 0
    assert row.nps > 0
    assert chess.Move.from_uci(row.move) in board.legal_moves
    assert row.depth == 1
    assert row.problem is None


@pytest.mark.parametrize("limits", [[], ["--depth", "2", "--time", "1"]])
def test_cli_needs_exactly_one_limit(tmp_path, limits):
    with pytest.raises(SystemExit) as exc:
        main(["--engine", "greedy", *limits, "--out", str(tmp_path / "x")])
    assert exc.value.code == 2


def test_cli_run(tmp_path):
    out = tmp_path / "b"
    main(["--engine", "greedy", "--depth", "1", "--positions", "openings", "--out", str(out)])
    with (out / "bench.csv").open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 50
    assert list(rows[0]) == ["position", "fen", "move", "nodes", "depth", "score_cp", "time_s", "nps", "problem"]
    with (out / "summary.csv").open() as f:
        [summary] = list(csv.DictReader(f))
    assert summary["positions"] == "50"
    assert int(summary["total_nodes"]) > 0
    assert (out / "manifest.json").exists()
