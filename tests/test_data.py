from collections import Counter

import chess
import pytest

from chessai.data import load_openings, load_puzzles


def test_openings_bundled():
    openings = load_openings()
    assert len(openings) == 50
    assert len({o.name for o in openings}) == 50
    assert len({o.board().epd() for o in openings}) == 50
    for opening in openings:
        assert 4 <= len(opening.moves) <= 10, opening.name
        assert not opening.board().is_game_over(), opening.name


def test_opening_board_is_fresh():
    opening = load_openings()[0]
    first = opening.board()
    first.pop()
    assert len(opening.board().move_stack) == len(opening.moves)


def test_bad_line_reports_line_number(tmp_path):
    path = tmp_path / "openings.txt"
    path.write_text("Good | e4 e5\nBad | e4 e4\n")
    with pytest.raises(ValueError, match="line 2"):
        load_openings(path)


def test_comments_and_blanks(tmp_path):
    path = tmp_path / "openings.txt"
    path.write_text("# c\n\nX | d4\n")
    openings = load_openings(path)
    assert [o.name for o in openings] == ["X"]


PUZZLE_HEADER = "puzzle_id,category,fen,moves,rating,themes,url\n"


def test_puzzle_fields(tmp_path):
    path = tmp_path / "puzzles.csv"
    path.write_text(PUZZLE_HEADER + "abc12,mate1,6k1/5ppp/8/8/8/8/8/R3K3 b - - 0 1,g8h8 a1a8,900,"
                    "mate mateIn1,https://lichess.org/training/abc12\n")
    [puzzle] = load_puzzles(path)
    assert puzzle.puzzle_id == "abc12"
    assert puzzle.rating == 900
    assert puzzle.themes == ("mate", "mateIn1")
    assert puzzle.start_board().turn == chess.WHITE
    assert puzzle.solver_moves == (chess.Move.from_uci("a1a8"),)


def test_puzzle_illegal_move_rejected(tmp_path):
    path = tmp_path / "puzzles.csv"
    path.write_text(PUZZLE_HEADER + "bad99,mate1,6k1/5ppp/8/8/8/8/8/R3K3 b - - 0 1,g8h8 a1a9,900,"
                    "mate,https://lichess.org/training/bad99\n")
    with pytest.raises(ValueError, match="bad99"):
        load_puzzles(path)


def test_bundled_puzzles():
    puzzles = load_puzzles()
    assert len(puzzles) == 300
    assert Counter(p.category for p in puzzles) == {"mate1": 75, "mate2": 75, "mate3": 75, "material": 75}
    assert len({p.puzzle_id for p in puzzles}) == 300
    for puzzle in puzzles:
        if puzzle.category in ("mate1", "mate2", "mate3"):
            board = chess.Board(puzzle.fen)
            for move in puzzle.moves:
                board.push(move)
            assert board.is_checkmate(), puzzle.puzzle_id
            assert len(puzzle.solver_moves) == int(puzzle.category[-1])
        else:
            assert len(puzzle.solver_moves) in (1, 2, 3)


@pytest.mark.parametrize("text, problem", [
    ("A | e4 e5\nA | d4 d5\n", "name"),
    ("A | e4 e5 Nf3\nB | Nf3 e5 e4\n", "position"),
])
def test_duplicate_openings_rejected(tmp_path, text, problem):   # final review minor 2
    path = tmp_path / "openings.txt"
    path.write_text(text)
    with pytest.raises(ValueError, match=f"line 2.*{problem}"):
        load_openings(path)
