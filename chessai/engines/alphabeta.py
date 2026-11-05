"""Minimax and alpha-beta search. WRITTEN BY THE TEAM.

Work through the tutorials in order and make each step test pass:

    docs/learn/01-minimax.md           negamax                      tests/learn/test_step_01.py
    docs/learn/03-alpha-beta.md        alphabeta, root_search       tests/learn/test_step_03.py
    docs/learn/04-strong-alpha-beta.md order_moves, quiescence,     tests/learn/test_step_04.py
                                       the two engines

Conventions (the tests rely on them):
- Scores are centipawns from the SIDE TO MOVE's point of view (negamax form).
- Before looking at the depth, check `board.is_game_over()`: a checkmated
  side to move scores -(MATE_SCORE + depth); any other game end scores 0.
  (More depth left means the mate came sooner, so sooner mates score higher.)
- At depth 0, return `evaluate(board)`.
- Every function must leave `board` exactly as it found it (push, then pop).
"""
from __future__ import annotations

import random
import threading
from collections.abc import Callable
from typing import ClassVar

import chess

from chessai.engines.base import SearchLimit, SearchResult
from chessai.engines.evaluate import EVAL_NAME, EVAL_VERSION, MATE_SCORE  # noqa: F401  (you will need MATE_SCORE)

INFINITY = 1_000_000            # bigger than any score, including mates
# AlphaBetaEngine passes this as `quiesce`. Set it to False when you benchmark
# minimax against alpha-beta, so that both search exactly the same tree.
USE_QUIESCENCE = True
Evaluate = Callable[[chess.Board], int]


class SearchTimeout(Exception):
    """Raise this from deep inside a search when the deadline passes or `stop` is set."""


def negamax(board: chess.Board, depth: int, evaluate: Evaluate) -> int:
    """The minimax value of `board` searched `depth` plies deep, side to move's view.

    No pruning: it visits every position. Used to check alphabeta and to count
    how many positions pruning saves.
    """
    # Game over is checked before depth, so a mate on the horizon still scores as a mate.
    if board.is_game_over():
        if board.is_checkmate():
            return -(MATE_SCORE + depth)   # side to move is mated; sooner mates have more depth left
        return 0                           # stalemate, insufficient material, repetition, ...
    if depth == 0:
        return evaluate(board)

    best = -INFINITY
    for move in board.legal_moves:
        board.push(move)
        score = -negamax(board, depth - 1, evaluate)   # the child's score is from the opponent's view
        board.pop()
        best = max(best, score)
    return best


def alphabeta(board: chess.Board, depth: int, alpha: int, beta: int, evaluate: Evaluate,
              quiesce: bool = False) -> int:
    """Negamax with alpha-beta pruning inside the window (alpha, beta).

    With the full window (-INFINITY, INFINITY) it must return exactly what
    negamax returns. With quiesce=True, call `quiescence` instead of
    `evaluate` at depth 0 (tutorial 4); the step tests use quiesce=False.
    """
    raise NotImplementedError("alphabeta: see docs/learn/03-alpha-beta.md")


def order_moves(board: chess.Board) -> list[chess.Move]:
    """All legal moves, the most promising first (captures before quiet moves).

    Searching good moves first makes alpha-beta prune much more.
    """
    raise NotImplementedError("order_moves: see docs/learn/04-strong-alpha-beta.md")


def quiescence(board: chess.Board, alpha: int, beta: int, evaluate: Evaluate) -> int:
    """Keep searching captures only until the position is quiet.

    Stand pat on evaluate(board), then try captures only (board.is_capture).
    Do not test for checkmate or check here.
    """
    raise NotImplementedError("quiescence: see docs/learn/04-strong-alpha-beta.md")


def root_search(board: chess.Board, depth: int, evaluate: Evaluate,
                deadline: float | None = None,
                stop: threading.Event | None = None,
                quiesce: bool = False) -> tuple[chess.Move, int]:
    """The best move at `depth` and its score (side to move's view); `quiesce` as in alphabeta.

    If `deadline` (a time.perf_counter() value) passes or `stop` is set, raise
    SearchTimeout so the engine can fall back to the last finished depth.
    """
    raise NotImplementedError("root_search: see docs/learn/03-alpha-beta.md")


class MinimaxEngine:
    """Plain negamax to a fixed depth: the 'no pruning' baseline for the bench tool."""

    name: ClassVar[str] = "minimax"
    evaluation: ClassVar[str] = f"{EVAL_NAME} v{EVAL_VERSION}"

    def __init__(self, rng: random.Random) -> None:
        self.rng = rng

    def search(self, board: chess.Board, limit: SearchLimit, stop: threading.Event) -> SearchResult:
        """Search to limit.depth (3 if not set) with negamax; report nodes, depth and score."""
        raise NotImplementedError("MinimaxEngine.search: see docs/learn/04-strong-alpha-beta.md")


class AlphaBetaEngine:
    """Alpha-beta with iterative deepening: the team's main alpha-beta engine."""

    name: ClassVar[str] = "alphabeta"
    evaluation: ClassVar[str] = f"{EVAL_NAME} v{EVAL_VERSION}"

    def __init__(self, rng: random.Random) -> None:
        self.rng = rng

    def search(self, board: chess.Board, limit: SearchLimit, stop: threading.Event) -> SearchResult:
        """Deepen 1, 2, 3, ... until limit.depth, limit.time_s or `stop`; play the last
        finished depth's move. Use quiesce=USE_QUIESCENCE and the shared `evaluate`.
        Report depth, nodes, score_cp and pv in SearchInfo."""
        raise NotImplementedError("AlphaBetaEngine.search: see docs/learn/04-strong-alpha-beta.md")
