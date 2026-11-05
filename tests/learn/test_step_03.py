"""Step 3: alpha-beta. Read docs/learn/03-alpha-beta.md first.

Alpha-beta must give exactly the negamax value while looking at fewer positions.
"""
import chess
import pytest

from chessai.engines.alphabeta import INFINITY, alphabeta, negamax, root_search
from tests.learn._steps import counting, fixture_eval, load_fixture, step

TUTORIAL = "docs/learn/03-alpha-beta.md"
POSITIONS = load_fixture("negamax")["positions"]
IDS = [p["name"] for p in POSITIONS]
SHALLOW = [p for p in POSITIONS if p["depth"] <= 2]


@pytest.mark.parametrize("pos", POSITIONS, ids=IDS)
@step(TUTORIAL)
def test_full_window_equals_negamax(pos):
    board = chess.Board(pos["fen"])
    before = board.copy()
    assert alphabeta(board, pos["depth"], -INFINITY, INFINITY, fixture_eval) == pos["value"]
    assert board == before and board.move_stack == before.move_stack, "alphabeta must undo every move it pushes"


@pytest.mark.parametrize("pos", SHALLOW, ids=[p["name"] for p in SHALLOW])
@step(TUTORIAL)
def test_window(pos):
    """Inside the window: the exact value. Outside: at least the right side of the window."""
    v, depth, fen = pos["value"], pos["depth"], pos["fen"]
    assert alphabeta(chess.Board(fen), depth, v - 1, v + 1, fixture_eval) == v
    assert alphabeta(chess.Board(fen), depth, v, v + 50, fixture_eval) <= v, "fail low: the true value is <= alpha"
    assert alphabeta(chess.Board(fen), depth, v - 50, v, fixture_eval) >= v, "fail high: the true value is >= beta"


@step(TUTORIAL)
def test_prunes():
    """Alpha-beta never evaluates more positions than negamax, and in total clearly fewer."""
    pruned_total = full_total = 0
    for pos in SHALLOW:
        full, full_calls = counting(fixture_eval)
        pruned, pruned_calls = counting(fixture_eval)
        negamax(chess.Board(pos["fen"]), pos["depth"], full)
        alphabeta(chess.Board(pos["fen"]), pos["depth"], -INFINITY, INFINITY, pruned)
        assert pruned_calls[0] <= full_calls[0], pos["name"]
        pruned_total += pruned_calls[0]
        full_total += full_calls[0]
    assert pruned_total < full_total


@pytest.mark.parametrize("pos", [p for p in POSITIONS if p["best_moves"]],
                         ids=[p["name"] for p in POSITIONS if p["best_moves"]])
@step(TUTORIAL)
def test_root_search(pos):
    board = chess.Board(pos["fen"])
    move, score = root_search(board, pos["depth"], fixture_eval)
    assert score == pos["value"]
    assert move.uci() in pos["best_moves"], f"{move.uci()} is not one of the best moves {pos['best_moves']}"
    assert board.fen() == pos["fen"]
