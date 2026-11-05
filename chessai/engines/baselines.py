"""Two deliberately weak engines: a common yardstick for the real ones."""
from __future__ import annotations

import random
import threading

import chess

from chessai.engines.base import Candidate, SearchInfo, SearchLimit, SearchResult

PIECE_VALUES = {
    chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
    chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0,
}
MATE_SCORE = 10**6


def material(board: chess.Board, color: chess.Color) -> int:
    """Sum of piece values for one side (pawn 1, knight/bishop 3, rook 5, queen 9)."""
    return sum(
        value * len(board.pieces(piece_type, color))
        for piece_type, value in PIECE_VALUES.items()
    )


class RandomEngine:
    """Plays a uniformly random legal move."""

    name = "random"
    evaluation = "none"

    def __init__(self, rng: random.Random) -> None:
        self._rng = rng

    def search(self, board: chess.Board, limit: SearchLimit, stop: threading.Event) -> SearchResult:
        return SearchResult(self._rng.choice(list(board.legal_moves)), SearchInfo(nodes=1))


class GreedyEngine:
    """Looks one move ahead: mate if possible, else the best material balance."""

    name = "greedy"
    evaluation = "material 1/3/3/5/9"

    def __init__(self, rng: random.Random) -> None:
        self._rng = rng

    def search(self, board: chess.Board, limit: SearchLimit, stop: threading.Event) -> SearchResult:
        mover = board.turn
        moves = list(board.legal_moves)
        self._rng.shuffle(moves)  # ties go to whichever comes first: random but seeded
        scored = []
        for move in moves:
            board.push(move)
            if board.is_checkmate():
                score = MATE_SCORE
            else:
                score = material(board, mover) - material(board, not mover)
            board.pop()
            scored.append((score, move))
        ranked = sorted(scored, key=lambda pair: -pair[0])  # stable: shuffled order breaks ties
        best_score, best_move = ranked[0]
        info = SearchInfo(
            nodes=len(moves),
            depth=1,
            score_cp=best_score * 100,
            candidates=[Candidate(move, score_cp=score * 100) for score, move in ranked[:3]],
        )
        return SearchResult(best_move, info)
