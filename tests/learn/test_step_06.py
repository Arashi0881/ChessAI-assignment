"""Step 6: MCTS for chess. Read docs/learn/06-mcts-chess.md first."""
import math
import random
import threading
import time

import chess
import pytest

from chessai.data import load_puzzles
from chessai.engines.base import SearchLimit, allowed_time, engine_rng
from chessai.engines.mcts import MCTSEngine, Node, best_move, cp_to_win, rollout
from tests.learn._steps import run_engine, step

TUTORIAL = "docs/learn/06-mcts-chess.md"
MATED = "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3"   # White to move, checkmated
STALEMATE = "7k/5Q2/6K1/8/8/8/8/8 b - - 0 1"
ONE_MOVE = "7k/R7/8/8/8/8/8/K7 b - - 0 1"        # Black's only move is Kg8; the game goes on
MIDDLEGAME = "r1bqk1nr/pppp1ppp/2n5/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
MATE1 = [p for p in load_puzzles() if p.category == "mate1"][:5]


def plus_400(board):
    return 400


def engine(seed=0):
    return MCTSEngine(engine_rng(seed, "mcts"))


@step(TUTORIAL)
def test_cp_to_win():
    assert cp_to_win(0) == 0.5
    assert math.isclose(cp_to_win(400), 1 / 1.1, abs_tol=1e-9)
    for cp in (35, 120, 900):
        assert math.isclose(cp_to_win(cp) + cp_to_win(-cp), 1.0, abs_tol=1e-12)


@pytest.mark.parametrize("fen, plies, expected", [
    (MATED, 10, 0.0),              # the side to move is checkmated: a loss
    (STALEMATE, 10, 0.5),          # a draw
    (ONE_MOVE, 0, 1 / 1.1),        # no moves played: the evaluation, side to move's view
    (ONE_MOVE, 1, 1 - 1 / 1.1),    # one move: +400 is now the OPPONENT's view
], ids=["checkmated", "stalemate", "evaluation", "perspective"])
@step(TUTORIAL)
def test_rollout(fen, plies, expected):
    board = chess.Board(fen)
    before = board.copy()
    assert math.isclose(rollout(board, random.Random(0), plies, plus_400), expected, abs_tol=1e-9)
    assert board == before and board.move_stack == before.move_stack, "rollout must leave the board as it was"


@step(TUTORIAL)
def test_best_move_is_most_visited():
    board = chess.Board()
    root = Node.root(board)
    for uci, visits, value in (("e2e4", 3, 2.9), ("d2d4", 7, 3.0), ("g1f3", 5, 4.0)):
        root.children.append(Node(chess.Move.from_uci(uci), root, [], visits=visits, value_sum=value))
    assert best_move(root) == chess.Move.from_uci("d2d4"), "most visits, not best average"


@step(TUTORIAL)
def test_engine_iterations():
    board = chess.Board(MIDDLEGAME)
    out = run_engine(engine(), board, SearchLimit(iterations=300))
    assert out.ok, out.problem
    info = out.result.info
    assert info.nodes == 300, "info.nodes = iterations run"
    assert sum(c.visits for c in info.candidates) == 300, "every iteration visits one root child"
    assert all(0.0 <= c.value <= 1.0 for c in info.candidates)
    top = max(info.candidates, key=lambda c: c.visits)
    assert out.result.move == top.move


@step(TUTORIAL)
def test_engine_is_reproducible():
    board = chess.Board(MIDDLEGAME)
    first = run_engine(engine(3), board, SearchLimit(iterations=200))
    second = run_engine(engine(3), board, SearchLimit(iterations=200))
    assert first.result.move == second.result.move
    assert [c.visits for c in first.result.info.candidates] == [c.visits for c in second.result.info.candidates]


@step(TUTORIAL)
def test_engine_time_limit():
    limit = SearchLimit(time_s=0.3)
    out = run_engine(engine(), chess.Board(MIDDLEGAME), limit)
    assert out.result is not None, out.problem
    assert out.elapsed <= allowed_time(limit) + 0.5, f"took {out.elapsed:.2f} s for a 0.3 s limit"


@step(TUTORIAL)
def test_engine_stops_when_asked():
    stop = threading.Event()
    threading.Timer(0.2, stop.set).start()
    start = time.perf_counter()
    out = run_engine(engine(), chess.Board(MIDDLEGAME), SearchLimit(time_s=10), stop)
    assert time.perf_counter() - start < 1.5, "check `stop` once per iteration"
    assert out.result is not None


@step(TUTORIAL)
def test_engine_finds_mate_in_one():
    solved = 0
    for puzzle in MATE1:
        board = puzzle.start_board()
        out = run_engine(engine(), board, SearchLimit(iterations=1000))
        assert out.ok, out.problem
        board.push(out.result.move)
        solved += board.is_checkmate()
    assert solved >= 4, f"found mate in only {solved} of 5 mate-in-1 puzzles with 1000 iterations"
