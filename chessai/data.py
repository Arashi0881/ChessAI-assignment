"""The bundled data files: opening positions for matches and puzzles for the tactics test."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import chess

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@dataclass(frozen=True)
class Opening:
    name: str
    moves: tuple[chess.Move, ...]

    def board(self) -> chess.Board:
        """A fresh board with the opening moves played."""
        board = chess.Board()
        for move in self.moves:
            board.push(move)
        return board


def load_openings(path: Path = DATA_DIR / "openings.txt") -> list[Opening]:
    """Read `Name | SAN moves` lines; `#` comments and blank lines are ignored."""
    openings = []
    names: set[str] = set()
    positions: dict[str, str] = {}   # a match counts each opening as independent: no repeats
    for number, raw in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        name, sep, sans = (part.strip() for part in line.partition("|"))
        if not sep or not name or not sans:
            raise ValueError(f"openings.txt line {number}: expected 'Name | moves', got {raw!r}")
        board = chess.Board()
        moves = []
        for san in sans.split():
            try:
                moves.append(board.push_san(san))
            except ValueError:
                raise ValueError(f"openings.txt line {number}: illegal move {san!r} in {name}") from None
        if name in names:
            raise ValueError(f"openings.txt line {number}: duplicate name {name!r}")
        if board.epd() in positions:
            raise ValueError(f"openings.txt line {number}: {name} reaches the same position as "
                             f"{positions[board.epd()]}")
        names.add(name)
        positions[board.epd()] = name
        openings.append(Opening(name, tuple(moves)))
    return openings


@dataclass(frozen=True)
class Puzzle:
    """A Lichess puzzle. `moves[0]` is the opponent's move; then solver and opponent alternate."""

    puzzle_id: str
    category: str               # mate1, mate2, mate3 or material
    fen: str                    # position before the opponent's first move
    moves: tuple[chess.Move, ...]
    rating: int
    themes: tuple[str, ...]
    url: str

    def start_board(self) -> chess.Board:
        """The position the solver faces: the FEN with the opponent's first move played."""
        board = chess.Board(self.fen)
        board.push(self.moves[0])
        return board

    @property
    def solver_moves(self) -> tuple[chess.Move, ...]:
        return self.moves[1::2]


def load_puzzles(path: Path = DATA_DIR / "puzzles.csv") -> list[Puzzle]:
    """Read the puzzle CSV, checking that every puzzle's moves are legal in sequence."""
    puzzles = []
    with Path(path).open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            pid = row["puzzle_id"]
            try:
                board = chess.Board(row["fen"])
                moves = []
                for uci in row["moves"].split():
                    move = chess.Move.from_uci(uci)
                    if move not in board.legal_moves:
                        raise ValueError(f"illegal move {uci}")
                    board.push(move)
                    moves.append(move)
                if len(moves) < 2:
                    raise ValueError("needs the opponent's move and at least one solver move")
                rating = int(row["rating"])
            except ValueError as exc:
                raise ValueError(f"puzzle {pid}: {exc}") from None
            puzzles.append(Puzzle(pid, row["category"], row["fen"], tuple(moves), rating,
                                  tuple(row["themes"].split()), row["url"]))
    return puzzles
