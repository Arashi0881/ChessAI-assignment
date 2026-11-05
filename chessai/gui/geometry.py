"""Board geometry and click-to-move helpers (no tkinter, unit-tested).

The board is drawn from pixel (0, 0) with 8 × 8 squares of `size` pixels,
rank 8 at the top unless `flipped`.
"""
from __future__ import annotations

import chess

GLYPHS = {
    "K": "♔", "Q": "♕", "R": "♖", "B": "♗", "N": "♘", "P": "♙",
    "k": "♚", "q": "♛", "r": "♜", "b": "♝", "n": "♞", "p": "♟",
}


def square_at(x: float, y: float, size: int, flipped: bool) -> chess.Square | None:
    if x < 0 or y < 0:
        return None
    col, row = int(x // size), int(y // size)
    if col > 7 or row > 7:
        return None
    if flipped:
        return chess.square(7 - col, row)
    return chess.square(col, 7 - row)


def square_origin(square: chess.Square, size: int, flipped: bool) -> tuple[int, int]:
    file, rank = chess.square_file(square), chess.square_rank(square)
    col, row = (7 - file, rank) if flipped else (file, 7 - rank)
    return col * size, row * size


def square_center(square: chess.Square, size: int, flipped: bool) -> tuple[float, float]:
    x, y = square_origin(square, size, flipped)
    return x + size / 2, y + size / 2


def piece_text(piece: chess.Piece, letters: bool) -> str:
    """Unicode chess symbol, or the letter (K/k …) when the font lacks the symbols."""
    symbol = piece.symbol()
    return symbol if letters else GLYPHS[symbol]


def targets(board: chess.Board, from_square: chess.Square) -> set[chess.Square]:
    return {m.to_square for m in board.legal_moves if m.from_square == from_square}


def needs_promotion(board: chess.Board, from_square: chess.Square, to_square: chess.Square) -> bool:
    return any(
        m.from_square == from_square and m.to_square == to_square and m.promotion
        for m in board.legal_moves
    )


def find_move(
    board: chess.Board,
    from_square: chess.Square,
    to_square: chess.Square,
    promotion: chess.PieceType | None = None,
) -> chess.Move | None:
    move = chess.Move(from_square, to_square, promotion=promotion)
    return move if move in board.legal_moves else None


# Fonts known to contain the chess symbols U+2654–U+265F, most preferred first:
# Windows, macOS, then common Linux fonts. Tk does not reliably fall back to a
# font that has them (on Linux it can pick a colour-emoji font it cannot draw).
PIECE_FONTS = (
    "Segoe UI Symbol",
    "Apple Symbols",
    "Arial Unicode MS",
    "DejaVu Sans",
    "Noto Sans Symbols 2",
    "Noto Sans Symbols2",
    "FreeSerif",
    "Symbola",
)


def pick_piece_font(available) -> str | None:
    """First font from PIECE_FONTS that is installed; None means use letters."""
    families = set(available)
    return next((name for name in PIECE_FONTS if name in families), None)
