import csv

import chess
import pytest

from chessai.data import Puzzle, load_puzzles
from chessai.engines import GreedyEngine
from chessai.engines.base import SearchInfo, SearchLimit, SearchResult, engine_rng
from chessai.puzzles import main, solve_puzzle

LIMIT = SearchLimit(time_s=0.2)
TWO_MATES = "6k1/6pp/8/8/8/8/8/RR4K1 b - - 0 1"   # after ...Kh8 both Ra8# and Rb8# mate


def puzzle(fen, ucis, category="mate1"):
    moves = tuple(chess.Move.from_uci(u) for u in ucis)
    return Puzzle("test1", category, fen, moves, 1000, (), "")


class Plays:
    """Plays the given UCI moves in order, one per search."""

    name = "plays"

    def __init__(self, *ucis, nodes=5):
        self.moves = list(ucis)
        self.nodes = nodes

    def search(self, board, limit, stop):
        return SearchResult(chess.Move.from_uci(self.moves.pop(0)), SearchInfo(nodes=self.nodes))


def mates(board, move):
    board.push(move)
    try:
        return board.is_checkmate()
    finally:
        board.pop()


def test_greedy_solves_mate_in_one():
    result = solve_puzzle(puzzle(TWO_MATES, ["g8h8", "a1a8"]), GreedyEngine(engine_rng(0, "g")), LIMIT)
    assert result.solved
    assert result.failed_at is None
    assert result.problem is None


def test_other_mating_move_accepted():
    result = solve_puzzle(puzzle(TWO_MATES, ["g8h8", "a1a8"]), Plays("b1b8", nodes=7), LIMIT)
    assert result.solved
    assert result.played == ("b1b8",)
    assert result.expected == ("a1a8",)
    assert result.nodes == 7


def test_wrong_move_fails():
    result = solve_puzzle(puzzle(TWO_MATES, ["g8h8", "a1a8"]), Plays("a1a7"), LIMIT)
    assert not result.solved
    assert result.failed_at == 0
    assert result.played == ("a1a7",)


def test_second_move_wrong():
    two = next(p for p in load_puzzles() if p.category == "mate2")
    board = two.start_board()
    board.push(two.solver_moves[0])
    board.push(two.moves[2])
    wrong = next(m for m in board.legal_moves if m != two.solver_moves[1] and not mates(board, m))
    result = solve_puzzle(two, Plays(two.solver_moves[0].uci(), wrong.uci()), LIMIT)
    assert not result.solved
    assert result.failed_at == 1
    assert len(result.played) == 2


def test_illegal_move_is_a_problem():
    result = solve_puzzle(puzzle(TWO_MATES, ["g8h8", "a1a8"]), Plays("h2h4"), LIMIT)
    assert not result.solved
    assert result.failed_at == 0
    assert result.problem.startswith("illegal")


def test_cli(tmp_path, capsys):
    out = tmp_path / "p"
    main(["--engine", "greedy", "--time", "0.1", "--category", "mate1", "--limit", "3", "--out", str(out)])
    with (out / "puzzles.csv").open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 3
    assert list(rows[0]) == ["puzzle_id", "category", "rating", "solved", "failed_at", "played",
                             "expected", "time_total", "nodes", "problem", "url"]
    with (out / "summary.csv").open() as f:
        summary = list(csv.DictReader(f))
    assert list(summary[0]) == ["category", "puzzles", "solved", "rate", "rate_low", "rate_high", "time_per_move"]
    assert [r["category"] for r in summary] == ["mate1", "all"]
    assert summary[0]["solved"] == "3"   # greedy always finds mate in one
    assert (out / "manifest.json").exists()
    assert "mate1" in capsys.readouterr().out


@pytest.mark.parametrize("extra", [["--engine", "nobody"], ["--engine", "greedy", "--category", "mate9"],
                                   ["--engine", "greedy", "--time", "inf"]])
def test_cli_rejects_bad_input(tmp_path, extra):
    with pytest.raises(SystemExit) as exc:
        main([*extra, "--out", str(tmp_path / "x")])
    assert exc.value.code == 2


def test_engine_killing_its_process_fails_the_puzzle():     # final review #2/#4
    from chessai.puzzles import run_puzzles
    puzzles = [p for p in load_puzzles() if p.category == "mate1"][:2]
    results = run_puzzles(puzzles, "exit-test", LIMIT, seed=0, jobs=2, engine_module="tests.fake_engines")
    assert [r.puzzle_id for r in results] == [p.puzzle_id for p in puzzles]
    assert all(not r.solved and r.failed_at == 0 and r.problem.startswith("crash") for r in results)


def test_sys_exit_engine_fails_the_puzzle():                  # final review #3
    class SysExit(Plays):
        def search(self, board, limit, stop):
            raise SystemExit
    result = solve_puzzle(puzzle(TWO_MATES, ["g8h8", "a1a8"]), SysExit(), LIMIT)
    assert not result.solved
    assert result.problem.startswith("engine error")


def test_interrupted_puzzles_keep_results(tmp_path, monkeypatch):   # final review #1
    import chessai.puzzles as cli
    real = cli.run_puzzles

    def interrupted(puzzles, engine, limit, seed, jobs, progress=None, engine_module=None):
        real(puzzles[:2], engine, limit, seed, 1, progress)
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "run_puzzles", interrupted)
    out = tmp_path / "p"
    with pytest.raises(SystemExit) as exc:
        main(["--engine", "greedy", "--time", "0.1", "--category", "mate1", "--limit", "5", "--out", str(out)])
    assert exc.value.code == 130
    with (out / "puzzles.csv").open() as f:
        assert len(list(csv.DictReader(f))) == 2
    with (out / "summary.csv").open() as f:
        assert next(csv.DictReader(f))["puzzles"] == "2"
