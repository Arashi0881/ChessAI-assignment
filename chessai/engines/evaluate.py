"""The evaluation function shared by both engines. WRITTEN BY THE TEAM.

Read docs/learn/02-evaluation.md, then make tests/learn/test_step_02.py pass.

Both alpha-beta and MCTS import `evaluate` from here, so a head-to-head match
compares the two search methods, not two different evaluations.

Convention (used everywhere): scores are in centipawns (100 = one pawn) from
the point of view of the SIDE TO MOVE. +150 means the player about to move
is a pawn and a half ahead.
"""
from __future__ import annotations

import chess

MATE_SCORE = 100_000   # a checkmate; larger than any evaluation can be

# Recorded in every match (games.csv, white_eval / black_eval). Change the name
# or bump the version whenever you change the evaluation, so results made with
# different evaluations are never mixed up.
EVAL_NAME = "material+pst"
EVAL_VERSION = 1

# Your piece values in centipawns, e.g. {chess.PAWN: 100, ...}. See tutorial 2.
PIECE_VALUES: dict[chess.PieceType, int] = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,      # never captured; checkmate is scored by the search
}


def material(board: chess.Board) -> int:
    """Material balance in centipawns: side to move's pieces minus the opponent's.

    The start position is 0. Use PIECE_VALUES; the king counts 0.
    """
    us, them = board.turn, not board.turn
    total = 0
    for piece_type, value in PIECE_VALUES.items():
        # pieces_mask is a 64-bit bitboard; counting its bits is much faster than len(board.pieces(...))
        count = (board.pieces_mask(piece_type, us).bit_count()
                 - board.pieces_mask(piece_type, them).bit_count())
        total += value * count
    return total


# Piece-square tables: the Chess Programming Wiki's "Simplified Evaluation
# Function" (Tomasz Michniewski). Each table is written from WHITE's point of
# view as you see the board: the first row is rank 8, the last row rank 1.
# _index() turns them into python-chess order (a1 = 0) at import time.
_PST_DIAGRAMS: dict[str, tuple[int, ...]] = {
    "pawn": (
          0,   0,   0,   0,   0,   0,   0,   0,
         50,  50,  50,  50,  50,  50,  50,  50,
         10,  10,  20,  30,  30,  20,  10,  10,
          5,   5,  10,  25,  25,  10,   5,   5,
          0,   0,   0,  20,  20,   0,   0,   0,
          5,  -5, -10,   0,   0, -10,  -5,   5,
          5,  10,  10, -20, -20,  10,  10,   5,
          0,   0,   0,   0,   0,   0,   0,   0,
    ),
    "knight": (
        -50, -40, -30, -30, -30, -30, -40, -50,
        -40, -20,   0,   0,   0,   0, -20, -40,
        -30,   0,  10,  15,  15,  10,   0, -30,
        -30,   5,  15,  20,  20,  15,   5, -30,
        -30,   0,  15,  20,  20,  15,   0, -30,
        -30,   5,  10,  15,  15,  10,   5, -30,
        -40, -20,   0,   5,   5,   0, -20, -40,
        -50, -40, -30, -30, -30, -30, -40, -50,
    ),
    "bishop": (
        -20, -10, -10, -10, -10, -10, -10, -20,
        -10,   0,   0,   0,   0,   0,   0, -10,
        -10,   0,   5,  10,  10,   5,   0, -10,
        -10,   5,   5,  10,  10,   5,   5, -10,
        -10,   0,  10,  10,  10,  10,   0, -10,
        -10,  10,  10,  10,  10,  10,  10, -10,
        -10,   5,   0,   0,   0,   0,   5, -10,
        -20, -10, -10, -10, -10, -10, -10, -20,
    ),
    "rook": (
          0,   0,   0,   0,   0,   0,   0,   0,
          5,  10,  10,  10,  10,  10,  10,   5,
         -5,   0,   0,   0,   0,   0,   0,  -5,
         -5,   0,   0,   0,   0,   0,   0,  -5,
         -5,   0,   0,   0,   0,   0,   0,  -5,
         -5,   0,   0,   0,   0,   0,   0,  -5,
         -5,   0,   0,   0,   0,   0,   0,  -5,
          0,   0,   0,   5,   5,   0,   0,   0,
    ),
    "queen": (
        -20, -10, -10,  -5,  -5, -10, -10, -20,
        -10,   0,   0,   0,   0,   0,   0, -10,
        -10,   0,   5,   5,   5,   5,   0, -10,
         -5,   0,   5,   5,   5,   5,   0,  -5,
          0,   0,   5,   5,   5,   5,   0,  -5,
        -10,   5,   5,   5,   5,   5,   0, -10,
        -10,   0,   5,   0,   0,   0,   0, -10,
        -20, -10, -10,  -5,  -5, -10, -10, -20,
    ),
    "king_middlegame": (   # stay castled behind the pawns
        -30, -40, -40, -50, -50, -40, -40, -30,
        -30, -40, -40, -50, -50, -40, -40, -30,
        -30, -40, -40, -50, -50, -40, -40, -30,
        -30, -40, -40, -50, -50, -40, -40, -30,
        -20, -30, -30, -40, -40, -30, -30, -20,
        -10, -20, -20, -20, -20, -20, -20, -10,
         20,  20,   0,   0,   0,   0,  20,  20,
         20,  30,  10,   0,   0,  10,  30,  20,
    ),
    "king_endgame": (      # few pieces left: the king walks to the centre
        -50, -40, -30, -20, -20, -30, -40, -50,
        -30, -20, -10,   0,   0, -10, -20, -30,
        -30, -10,  20,  30,  30,  20, -10, -30,
        -30, -10,  30,  40,  40,  30, -10, -30,
        -30, -10,  30,  40,  40,  30, -10, -30,
        -30, -10,  20,  30,  30,  20, -10, -30,
        -30, -30,   0,   0,   0,   0, -30, -30,
        -50, -30, -30, -30, -30, -30, -30, -50,
    ),
}


def _index(diagram: tuple[int, ...]) -> tuple[int, ...]:
    """A diagram (rank 8 first) as a table indexed by python-chess square (a1 = 0)."""
    assert len(diagram) == 64
    return tuple(diagram[chess.square_mirror(square)] for square in chess.SQUARES)


# PST[piece_type] is looked up with the square as WHITE sees it: a White piece
# uses its own square, a Black piece chess.square_mirror(square).
PST: dict[chess.PieceType, tuple[int, ...]] = {
    chess.PAWN: _index(_PST_DIAGRAMS["pawn"]),
    chess.KNIGHT: _index(_PST_DIAGRAMS["knight"]),
    chess.BISHOP: _index(_PST_DIAGRAMS["bishop"]),
    chess.ROOK: _index(_PST_DIAGRAMS["rook"]),
    chess.QUEEN: _index(_PST_DIAGRAMS["queen"]),
}
KING_MIDDLEGAME = _index(_PST_DIAGRAMS["king_middlegame"])
KING_ENDGAME = _index(_PST_DIAGRAMS["king_endgame"])


def is_endgame(board: chess.Board) -> bool:
    """The Simplified Evaluation Function's rule: no queens, or every side that
    has a queen has no rooks and at most one minor piece besides it."""
    for color in chess.COLORS:
        if board.pieces_mask(chess.QUEEN, color):
            minors = (board.pieces_mask(chess.KNIGHT, color)
                      | board.pieces_mask(chess.BISHOP, color)).bit_count()
            if board.pieces_mask(chess.ROOK, color) or minors > 1:
                return False
    return True


def _pst_for(board: chess.Board, color: chess.Color, king_table: tuple[int, ...]) -> int:
    """Material plus square bonuses for one side's pieces."""
    total = 0
    for piece_type, table in PST.items():
        value = PIECE_VALUES[piece_type]
        for square in chess.scan_forward(board.pieces_mask(piece_type, color)):
            total += value + table[square if color == chess.WHITE else chess.square_mirror(square)]
    king = board.king(color)
    if king is not None:
        total += king_table[king if color == chess.WHITE else chess.square_mirror(king)]
    return total


def evaluate(board: chess.Board) -> int:
    """How good `board` is for the side to move, in centipawns.

    Start with material; add piece-square tables or other terms if you like
    (tutorial 2). Only called on positions that are not game over: the
    searches handle checkmate and draws themselves. Must be symmetric:
    evaluate(board) == evaluate(board.mirror()).
    """
    king_table = KING_ENDGAME if is_endgame(board) else KING_MIDDLEGAME
    return (_pst_for(board, board.turn, king_table)
            - _pst_for(board, not board.turn, king_table))
