"""One game: the moves played, undo/redo, how it ended, and its PGN. No GUI here."""
from __future__ import annotations

from dataclasses import dataclass

import chess
import chess.pgn

_REASONS = {
    chess.Termination.CHECKMATE: "checkmate",
    chess.Termination.STALEMATE: "stalemate",
    chess.Termination.INSUFFICIENT_MATERIAL: "insufficient material",
    chess.Termination.SEVENTYFIVE_MOVES: "75-move rule",
    chess.Termination.FIVEFOLD_REPETITION: "fivefold repetition",
}


@dataclass(frozen=True)
class GameEnd:
    result: str  # "1-0", "0-1" or "1/2-1/2"
    reason: str


class GameSession:
    def __init__(self, fen: str = chess.STARTING_FEN) -> None:
        try:
            board = chess.Board(fen)
        except ValueError as exc:
            raise ValueError(f"invalid FEN: {exc}") from None
        if not board.is_valid():
            raise ValueError(f"illegal position: {board.status()!r}")
        self._board = board
        self._start_fen = board.fen()
        self._redo: list[chess.Move] = []

    @property
    def board(self) -> chess.Board:
        """The live board. Read it; change it only through play/undo/redo."""
        return self._board

    @property
    def start_fen(self) -> str:
        return self._start_fen

    @property
    def fen(self) -> str:
        return self._board.fen()

    @property
    def can_undo(self) -> bool:
        return bool(self._board.move_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    @property
    def last_move(self) -> chess.Move | None:
        return self._board.move_stack[-1] if self._board.move_stack else None

    def play(self, move: chess.Move) -> None:
        if self.outcome() is not None:
            raise ValueError("game is over")
        if move not in self._board.legal_moves:
            raise ValueError(f"illegal move: {move.uci()}")
        self._board.push(move)
        self._redo.clear()

    def undo(self) -> chess.Move | None:
        if not self.can_undo:
            return None
        move = self._board.pop()
        self._redo.append(move)
        return move

    def redo(self) -> chess.Move | None:
        if not self.can_redo:
            return None
        move = self._redo.pop()
        self._board.push(move)
        return move

    def outcome(self) -> GameEnd | None:
        outcome = self._board.outcome(claim_draw=False)
        if outcome is None:
            return None
        return GameEnd(outcome.result(), _REASONS.get(outcome.termination, outcome.termination.name.lower()))

    def san_moves(self) -> list[str]:
        replay = chess.Board(self._start_fen)
        sans = []
        for move in self._board.move_stack:
            sans.append(replay.san(move))
            replay.push(move)
        return sans

    def pgn(self, white: str, black: str) -> str:
        game = chess.pgn.Game.from_board(self._board)
        game.headers["White"] = white
        game.headers["Black"] = black
        end = self.outcome()
        game.headers["Result"] = end.result if end else "*"
        return str(game)
