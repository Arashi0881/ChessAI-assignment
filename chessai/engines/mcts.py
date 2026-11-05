"""Monte Carlo Tree Search. WRITTEN BY THE TEAM.

    docs/learn/05-mcts.md        uct_score, select, expand, backpropagate   tests/learn/test_step_05.py
    docs/learn/06-mcts-chess.md  cp_to_win, rollout, best_move, the engine  tests/learn/test_step_06.py

Conventions (the tests rely on them):
- Values are win probabilities in [0, 1]: 1 = win, 0.5 = draw, 0 = loss.
- `Node.value_sum` is from the point of view of the player who MADE
  `node.move` (the player to move at the parent). A parent therefore picks
  the child with the best value_sum / visits for itself.
- `rollout` and `backpropagate` take and return values from the point of
  view of the SIDE TO MOVE in that node's position.
"""
from __future__ import annotations

import random
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import ClassVar

import chess

from chessai.engines.base import SearchLimit, SearchResult
from chessai.engines.evaluate import EVAL_NAME, EVAL_VERSION

EXPLORATION = 1.4      # the constant c in UCT; tune it with the match tool
ROLLOUT_PLIES = 10     # random moves per rollout before asking the evaluation

Evaluate = Callable[[chess.Board], int]


@dataclass(eq=False)
class Node:
    """One position in the search tree. The position itself is not stored:
    replay the moves from the root (select/expand push them on a board)."""

    move: chess.Move | None              # the move that led here; None at the root
    parent: Node | None
    untried: list[chess.Move]            # legal moves with no child yet
    children: list[Node] = field(default_factory=list)
    visits: int = 0
    value_sum: float = 0.0               # from the view of the player who made `move`

    @classmethod
    def root(cls, board: chess.Board) -> Node:
        return cls(None, None, list(board.legal_moves))


def uct_score(value_sum: float, visits: int, parent_visits: int, c: float) -> float:
    """UCT: average value plus an exploration bonus. math.inf for an unvisited child."""
    raise NotImplementedError("uct_score: see docs/learn/05-mcts.md")


def select(node: Node, board: chess.Board, c: float) -> Node:
    """From `node`, follow the child with the highest UCT score while the node is
    fully expanded (no untried moves) and has children. Push every move you
    follow onto `board`. Return the node where you stopped."""
    raise NotImplementedError("select: see docs/learn/05-mcts.md")


def expand(node: Node, board: chess.Board, rng: random.Random) -> Node:
    """Take one untried move (chosen with `rng`), push it on `board`, attach and
    return the new child. If there are no untried moves (game over), return `node`."""
    raise NotImplementedError("expand: see docs/learn/05-mcts.md")


def cp_to_win(cp: int) -> float:
    """Turn a centipawn score into a win probability: 1 / (1 + 10 ** (-cp / 400))."""
    raise NotImplementedError("cp_to_win: see docs/learn/06-mcts-chess.md")


def rollout(board: chess.Board, rng: random.Random, max_plies: int, evaluate: Evaluate) -> float:
    """Play up to `max_plies` moves (chosen with `rng`) from `board`, then score it.

    Returns the value for the side to move in `board` AT THE START: the real
    result if the game ends, otherwise cp_to_win(evaluate(...)) converted to
    that side's view. Leave `board` as you found it.
    """
    raise NotImplementedError("rollout: see docs/learn/06-mcts-chess.md")


def backpropagate(node: Node, value: float) -> None:
    """Add one visit and the result to `node` and every ancestor up to the root.

    `value` is for the side to move at `node`'s position; remember that
    value_sum is stored for the player who moved INTO each node.
    """
    raise NotImplementedError("backpropagate: see docs/learn/05-mcts.md")


def best_move(root: Node) -> chess.Move:
    """The move to play: the root child with the most visits."""
    raise NotImplementedError("best_move: see docs/learn/06-mcts-chess.md")


class MCTSEngine:
    """The team's MCTS engine."""

    name: ClassVar[str] = "mcts"
    evaluation: ClassVar[str] = f"{EVAL_NAME} v{EVAL_VERSION}"

    def __init__(self, rng: random.Random) -> None:
        self.rng = rng

    def search(self, board: chess.Board, limit: SearchLimit, stop: threading.Event) -> SearchResult:
        """Run select / expand / rollout / backpropagate until limit.iterations,
        limit.time_s or `stop`. Report info.nodes = iterations run and one
        Candidate(move, visits, value) per root child (value from the root
        mover's view)."""
        raise NotImplementedError("MCTSEngine.search: see docs/learn/06-mcts-chess.md")
