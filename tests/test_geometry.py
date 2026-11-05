import chess
import pytest

from chessai.gui.geometry import (
    find_move, needs_promotion, piece_text, square_at, square_center, square_origin, targets,
)

PROMO = "8/P6k/8/8/8/8/8/K7 w - - 0 1"
CAPTURE_PROMO = "1n6/P6k/8/8/8/8/8/K7 w - - 0 1"


@pytest.mark.parametrize("x,y,flipped,expected", [
    (0, 0, False, chess.A8), (399, 399, False, chess.H1), (0, 0, True, chess.H1),
    (399, 399, True, chess.A8), (400, 10, False, None), (-1, 10, False, None), (10, 400, False, None),
])
def test_square_at(x, y, flipped, expected):
    assert square_at(x, y, 50, flipped) == expected


@pytest.mark.parametrize("flipped", [False, True])
def test_center_round_trip(flipped):
    for sq in chess.SQUARES:
        assert square_at(*square_center(sq, 60, flipped), 60, flipped) == sq


def test_square_origin():
    assert square_origin(chess.A8, 50, False) == (0, 0)
    assert square_origin(chess.A1, 50, False) == (0, 350)
    assert square_origin(chess.A1, 50, True) == (350, 0)


def test_piece_text():
    assert piece_text(chess.Piece(chess.KING, chess.WHITE), False) == "♔"
    assert piece_text(chess.Piece(chess.PAWN, chess.BLACK), False) == "♟"
    assert piece_text(chess.Piece(chess.KING, chess.WHITE), True) == "K"
    assert piece_text(chess.Piece(chess.KING, chess.BLACK), True) == "k"


def test_targets():
    assert targets(chess.Board(), chess.G1) == {chess.F3, chess.H3}
    assert targets(chess.Board(), chess.E4) == set()


def test_promotion_detection():                       # Review Focus 1
    b = chess.Board(PROMO)
    assert needs_promotion(b, chess.A7, chess.A8)
    assert find_move(b, chess.A7, chess.A8) is None
    assert find_move(b, chess.A7, chess.A8, chess.KNIGHT) == chess.Move.from_uci("a7a8n")
    assert needs_promotion(chess.Board(CAPTURE_PROMO), chess.A7, chess.B8)
    assert not needs_promotion(chess.Board(), chess.E2, chess.E4)


def test_find_move_plain_and_illegal():
    b = chess.Board()
    assert find_move(b, chess.E2, chess.E4) == chess.Move.from_uci("e2e4")
    assert find_move(b, chess.E2, chess.E5) is None


def test_pick_piece_font_prefers_platform_symbol_fonts():
    from chessai.gui.geometry import pick_piece_font
    assert pick_piece_font({"Nunito", "Segoe UI Symbol", "DejaVu Sans"}) == "Segoe UI Symbol"
    assert pick_piece_font({"Helvetica", "Apple Symbols"}) == "Apple Symbols"
    assert pick_piece_font({"Nunito", "Noto Sans Symbols 2", "FreeSerif"}) == "Noto Sans Symbols 2"
    assert pick_piece_font({"Nunito", "Cantarell"}) is None      # → letters mode
