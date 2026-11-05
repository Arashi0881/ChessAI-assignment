"""Step 4: a strong alpha-beta engine. Read docs/learn/04-strong-alpha-beta.md first.

Move ordering, quiescence, time control, and the engine itself.
"""
import threading
import time

import chess
import pytest

from chessai.data import load_puzzles
from chessai.engines.alphabeta import (
    INFINITY, USE_QUIESCENCE, AlphaBetaEngine, MinimaxEngine, SearchTimeout, alphabeta, negamax, order_moves,
    quiescence, root_search,
)
from chessai.engines.evaluate import evaluate
from chessai.engines.base import SearchLimit, allowed_time, engine_rng
from chessai.engines.evaluate import MATE_SCORE
from tests.learn._steps import counting, fixture_eval, load_fixture, run_engine, step

TUTORIAL = "docs/learn/04-strong-alpha-beta.md"
POSITIONS = load_fixture("negamax")["positions"]
QUIET = load_fixture("quiescence")["positions"]
PAWN_TAKES_QUEEN = "rnb1kbnr/pppp1ppp/8/4q3/3P4/8/PPP1PPPP/RNBQKBNR w KQkq - 0 1"
MIDDLEGAME = "r1bqk1nr/pppp1ppp/2n5/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
# Share of negamax's evaluations alpha-beta may use on the depth-3 fixtures. Measured with
# a reference search: no ordering (python-chess's move order) 8.9%, captures first 2.8%,
# captures by victim value 4.0%. Any ordering that tries captures first passes.
ORDERING_LIMIT = 0.06
PUZZLES = load_puzzles()
MATE1 = [p for p in PUZZLES if p.category == "mate1"][:5]
MATE2 = [p for p in PUZZLES if p.category == "mate2"][:5]


def engine():
    return AlphaBetaEngine(engine_rng(0, "alphabeta"))


@step(TUTORIAL)
def test_order_moves_is_a_permutation():
    for fen in (PAWN_TAKES_QUEEN, MIDDLEGAME, chess.STARTING_FEN):
        board = chess.Board(fen)
        ordered = order_moves(board)
        assert sorted(m.uci() for m in ordered) == sorted(m.uci() for m in board.legal_moves)
        assert board.fen() == fen
    assert chess.Board(PAWN_TAKES_QUEEN).is_capture(order_moves(chess.Board(PAWN_TAKES_QUEEN))[0]), \
        "captures (here: pawn takes queen) should come first"


@step(TUTORIAL)
def test_ordering_makes_pruning_effective():
    deep = [p for p in POSITIONS if p["depth"] == 3]
    pruned_total = full_total = 0
    for pos in deep:
        full, full_calls = counting(fixture_eval)
        pruned, pruned_calls = counting(fixture_eval)
        negamax(chess.Board(pos["fen"]), 3, full)
        alphabeta(chess.Board(pos["fen"]), 3, -INFINITY, INFINITY, pruned)
        pruned_total += pruned_calls[0]
        full_total += full_calls[0]
    share = pruned_total / full_total
    assert share <= ORDERING_LIMIT, f"alpha-beta evaluated {share:.0%} of negamax's positions; order better moves first"


@pytest.mark.parametrize("pos", QUIET, ids=[f"q{i}" for i in range(len(QUIET))])
@step(TUTORIAL)
def test_quiescence(pos):
    board = chess.Board(pos["fen"])
    assert quiescence(board, -INFINITY, INFINITY, fixture_eval) == pos["value"]
    assert board.fen() == pos["fen"]


@step(TUTORIAL)
def test_quiescence_stands_pat_when_quiet():
    board = chess.Board()    # no captures possible
    assert quiescence(board, -INFINITY, INFINITY, fixture_eval) == fixture_eval(board)


@pytest.mark.parametrize("puzzle", MATE1, ids=[p.puzzle_id for p in MATE1])
@step(TUTORIAL)
def test_finds_mate_in_one(puzzle):
    board = puzzle.start_board()
    move, score = root_search(board, 1, fixture_eval)
    board.push(move)
    assert board.is_checkmate()
    assert score >= MATE_SCORE


@pytest.mark.parametrize("puzzle", MATE2, ids=[p.puzzle_id for p in MATE2])
@step(TUTORIAL)
def test_finds_mate_in_two(puzzle):
    move, score = root_search(puzzle.start_board(), 3, fixture_eval)
    assert move == puzzle.solver_moves[0]
    assert score >= MATE_SCORE


@step(TUTORIAL)
def test_root_search_respects_deadline():
    board = chess.Board(MIDDLEGAME)
    try:
        move, _ = root_search(board, 6, fixture_eval, deadline=time.perf_counter() - 1)
    except SearchTimeout:
        return
    assert move in board.legal_moves


@step(TUTORIAL)
def test_engine_depth_limit():
    board = chess.Board(MIDDLEGAME)
    out = run_engine(engine(), board, SearchLimit(depth=2))
    assert out.ok, out.problem
    info = out.result.info
    assert info.depth == 2
    assert info.nodes > 0
    assert info.score_cp is not None
    assert info.pv and info.pv[0] == out.result.move, "the PV starts with the move you play"


@step(TUTORIAL)
def test_engine_time_limit():
    limit = SearchLimit(time_s=0.3)
    out = run_engine(engine(), chess.Board(MIDDLEGAME), limit)
    assert out.result is not None and out.result.move in chess.Board(MIDDLEGAME).legal_moves, out.problem
    assert out.elapsed <= allowed_time(limit) + 0.5, f"took {out.elapsed:.2f} s for a 0.3 s limit"


@step(TUTORIAL)
def test_engine_stops_when_asked():
    stop = threading.Event()
    threading.Timer(0.2, stop.set).start()
    start = time.perf_counter()
    out = run_engine(engine(), chess.Board(MIDDLEGAME), SearchLimit(time_s=10), stop)
    assert time.perf_counter() - start < 1.5, "the engine must check `stop` while searching"
    assert out.result is not None and out.result.move in chess.Board(MIDDLEGAME).legal_moves


@step(TUTORIAL)
def test_engines_report_their_search_score():
    board = chess.Board(MIDDLEGAME)
    plain = run_engine(MinimaxEngine(engine_rng(0, "minimax")), board, SearchLimit(depth=2))
    pruned = run_engine(engine(), board, SearchLimit(depth=2))
    assert plain.ok and pruned.ok, (plain.problem, pruned.problem)
    assert plain.result.info.score_cp == negamax(board.copy(), 2, evaluate)
    assert pruned.result.info.score_cp == alphabeta(board.copy(), 2, -INFINITY, INFINITY, evaluate,
                                                    quiesce=USE_QUIESCENCE)
    assert plain.result.info.nodes > 0
