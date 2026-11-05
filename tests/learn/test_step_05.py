"""Step 5: the four MCTS steps. Read docs/learn/05-mcts.md first."""
import math
import random

import chess

from chessai.engines.mcts import Node, backpropagate, expand, select, uct_score
from tests.learn._steps import step

TUTORIAL = "docs/learn/05-mcts.md"


def child(parent, uci, board, visits=0, value_sum=0.0):
    """Attach a child to `parent` for the move `uci` played on `board` (pushed and popped)."""
    move = chess.Move.from_uci(uci)
    board.push(move)
    node = Node(move, parent, list(board.legal_moves), visits=visits, value_sum=value_sum)
    board.pop()
    parent.children.append(node)
    return node


@step(TUTORIAL)
def test_uct_score():
    assert math.isclose(uct_score(3, 4, 10, 1.4), 0.75 + 1.4 * math.sqrt(math.log(10) / 4), abs_tol=1e-9)
    assert math.isclose(uct_score(1, 2, 2, 1.0), 0.5 + math.sqrt(math.log(2) / 2), abs_tol=1e-9)
    assert uct_score(0, 0, 10, 1.4) == math.inf, "an unvisited child must be tried first"
    assert math.isclose(uct_score(3, 4, 10, 0), 0.75), "with c = 0 only the average counts"


@step(TUTORIAL)
def test_select_follows_highest_uct():
    board = chess.Board()
    root = Node(None, None, [], visits=10, value_sum=5.0)         # fully expanded
    child(root, "e2e4", board, visits=4, value_sum=2.0)           # UCT 1.56
    best = child(root, "d2d4", board, visits=3, value_sum=2.5)    # UCT 2.06: the highest
    child(root, "g1f3", board, visits=3, value_sum=1.0)           # UCT 1.56
    best.untried = []                                             # fully expanded too
    board.push(best.move)
    leaf = child(best, "e7e5", board, visits=1, value_sum=1.0)   # still has untried moves
    board.pop()

    walk = chess.Board()
    assert select(root, walk, 1.4) is leaf
    assert [m.uci() for m in walk.move_stack] == ["d2d4", "e7e5"], "push every move you follow"


@step(TUTORIAL)
def test_select_stops_at_node_with_untried_moves():
    board = chess.Board()
    root = Node.root(board)
    child(root, "e2e4", board, visits=5, value_sum=5.0)
    assert select(root, board, 1.4) is root
    assert board.move_stack == []


@step(TUTORIAL)
def test_expand():
    board = chess.Board()
    root = Node.root(board)
    before = list(root.untried)
    new = expand(root, board, random.Random(0))
    assert new.parent is root and root.children == [new]
    assert new.move in before and new.move not in root.untried
    assert len(root.untried) == len(before) - 1
    assert board.move_stack == [new.move], "push the move you expand"
    assert sorted(m.uci() for m in new.untried) == sorted(m.uci() for m in board.legal_moves)
    assert new.visits == 0 and new.value_sum == 0


@step(TUTORIAL)
def test_expand_terminal_returns_node():
    board = chess.Board("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")   # White is mated
    node = Node.root(board)
    assert expand(node, board, random.Random(0)) is node
    assert board.move_stack == []


@step(TUTORIAL)
def test_backpropagate_flips_perspective():
    board = chess.Board()
    root = Node.root(board)
    a = child(root, "e2e4", board)
    board.push(a.move)
    b = child(a, "e7e5", board)
    board.pop()
    # value 1.0: the side to move at b (White) wins, so Black, who moved into b, lost.
    backpropagate(b, 1.0)
    assert (b.visits, b.value_sum) == (1, 0.0)
    assert (a.visits, a.value_sum) == (1, 1.0), "White moved into a and wins"
    assert (root.visits, root.value_sum) == (1, 0.0)
    backpropagate(b, 0.5)
    assert (b.visits, b.value_sum) == (2, 0.5)
    assert (a.visits, a.value_sum) == (2, 1.5)
    assert (root.visits, root.value_sum) == (2, 0.5)
