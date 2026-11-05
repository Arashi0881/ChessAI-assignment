"""Step 1: negamax. Read docs/learn/01-minimax.md first.

Your negamax is run with a fixed material evaluation (fixture_eval) and must
return exactly the stored value for each position.
"""
import chess
import pytest

from chessai.engines.alphabeta import negamax
from chessai.engines.evaluate import MATE_SCORE
from tests.learn._steps import fixture_eval, load_fixture, step

TUTORIAL = "docs/learn/01-minimax.md"
POSITIONS = load_fixture("negamax")["positions"]


@pytest.mark.parametrize("pos", POSITIONS, ids=[p["name"] for p in POSITIONS])
@step(TUTORIAL)
def test_negamax_value(pos):
    board = chess.Board(pos["fen"])
    before = board.copy()
    assert negamax(board, pos["depth"], fixture_eval) == pos["value"]
    assert board == before and board.move_stack == before.move_stack, "negamax must undo every move it pushes"


@step(TUTORIAL)
def test_mate_scores():
    mate = next(p for p in POSITIONS if p["name"] == "mate in 1, depth 1")
    assert negamax(chess.Board(mate["fen"]), 1, fixture_eval) == MATE_SCORE
    mated = next(p for p in POSITIONS if p["name"] == "checkmated already")
    assert negamax(chess.Board(mated["fen"]), 1, fixture_eval) == -(MATE_SCORE + 1)
    assert negamax(chess.Board(mated["fen"]), 0, fixture_eval) == -MATE_SCORE


@step(TUTORIAL)
def test_depth_zero_is_the_evaluation():
    board = chess.Board("rnbqkb1r/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b KQkq - 0 1")
    assert negamax(board, 0, fixture_eval) == fixture_eval(board) == -300
