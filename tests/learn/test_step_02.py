"""Step 2: the evaluation. Read docs/learn/02-evaluation.md first.

Every team picks its own values, so these tests check properties any sound
evaluation has, not exact numbers.
"""
import chess

from chessai.engines.evaluate import EVAL_NAME, EVAL_VERSION, evaluate, material
from tests.learn._steps import step

TUTORIAL = "docs/learn/02-evaluation.md"
START = chess.Board()
NO_BLACK_KNIGHT = "r1bqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR {} KQkq - 0 1"
NO_BLACK_QUEEN = "rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR {} KQkq - 0 1"
MIDDLEGAME = [
    "r1bqk1nr/pppp1ppp/2n5/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
    "r2q1rk1/pp2bppp/2n1pn2/3p4/3P4/2NBPN2/PP3PPP/R2Q1RK1 b - - 3 10",
    "8/5pk1/6p1/3R4/8/6P1/5PK1/2r5 w - - 0 40",
]


@step(TUTORIAL)
def test_material():
    assert material(START.copy()) == 0
    assert isinstance(material(START.copy()), int)
    white_to_move = material(chess.Board(NO_BLACK_KNIGHT.format("w")))
    black_to_move = material(chess.Board(NO_BLACK_KNIGHT.format("b")))
    assert white_to_move > 0, "a knight up: positive for the side to move (White)"
    assert black_to_move == -white_to_move, "same position, Black to move: the same number, negated"
    assert material(chess.Board(NO_BLACK_QUEEN.format("w"))) > white_to_move, "a queen is worth more than a knight"


@step(TUTORIAL)
def test_evaluate_basics():
    value = evaluate(START.copy())
    assert isinstance(value, int)
    assert abs(value) < 50, "the start position is about equal"
    assert evaluate(chess.Board(NO_BLACK_QUEEN.format("w"))) > 500
    assert evaluate(chess.Board(NO_BLACK_QUEEN.format("b"))) < -500


@step(TUTORIAL)
def test_evaluate_is_symmetric():
    for fen in MIDDLEGAME + [NO_BLACK_KNIGHT.format("w")]:
        board = chess.Board(fen)
        assert evaluate(board) == evaluate(board.mirror()), f"colours swapped should score the same: {fen}"
        assert material(board) == material(board.mirror())


@step(TUTORIAL)
def test_evaluate_leaves_board_alone():
    board = chess.Board(MIDDLEGAME[0])
    before = board.fen()
    evaluate(board)
    assert board.fen() == before


def test_evaluation_is_named():
    assert isinstance(EVAL_NAME, str) and EVAL_NAME
    assert isinstance(EVAL_VERSION, int)
