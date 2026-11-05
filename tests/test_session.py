import chess
import pytest
from chessai.session import GameEnd, GameSession

M = chess.Move.from_uci


def test_play_undo_redo():
    s = GameSession()
    s.play(M("e2e4")); s.play(M("e7e5"))
    assert s.san_moves() == ["e4", "e5"] and s.last_move == M("e7e5")
    assert s.undo() == M("e7e5") and s.can_redo
    assert s.redo() == M("e7e5") and not s.can_redo
    s.undo(); s.play(M("c7c5"))
    assert not s.can_redo and s.san_moves() == ["e4", "c5"]


def test_illegal_move_rejected():
    with pytest.raises(ValueError):
        GameSession().play(M("e2e5"))


@pytest.mark.parametrize("fen,msg", [
    ("not a fen", "invalid FEN"),
    ("4k3/8/8/8/8/8/8/KK6 w - - 0 1", "illegal position"),    # Review Focus 3
])
def test_bad_fen(fen, msg):
    with pytest.raises(ValueError, match=msg):
        GameSession(fen)


def test_game_over_fen_has_outcome_and_blocks_moves():         # Review Focus 3
    s = GameSession("7k/6Q1/6K1/8/8/8/8/8 b - - 0 1")
    assert s.outcome() == GameEnd("1-0", "checkmate")
    with pytest.raises(ValueError):
        s.play(M("h8h7"))


def test_stalemate_reason():
    assert GameSession("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1").outcome() == GameEnd("1/2-1/2", "stalemate")


def test_pgn_from_custom_position():
    s = GameSession("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1")
    s.play(M("e2e4"))
    text = s.pgn("Alice", "greedy")
    assert '[White "Alice"]' in text and '[FEN "4k3/8/8/8/8/8/4P3/4K3 w - - 0 1"]' in text
    assert "1. e4" in text
