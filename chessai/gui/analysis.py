"""Turn an engine's SearchInfo into analysis text and arrows (no tkinter, unit-tested)."""
from __future__ import annotations

import chess

from chessai.engines.base import SearchInfo

MAX_CANDIDATE_LINES = 5
ARROW_WIDTHS = (8, 5, 3)


def format_score(score_cp: int | None, white_to_move: bool) -> str:
    """Engine score (side to move's view) shown from White's view in pawns: +1.20."""
    if score_cp is None:
        return "?"
    white_cp = score_cp if white_to_move else -score_cp
    return f"{white_cp / 100:+.2f}"


def _rate(nodes: int, elapsed: float) -> str:
    if elapsed <= 0:
        return "—"
    rate = nodes / elapsed
    if rate >= 1_000_000:
        return f"{rate / 1_000_000:.1f}M"
    if rate >= 1_000:
        return f"{rate / 1_000:.1f}k"
    return f"{rate:.0f}"


def _san_line(board: chess.Board, moves: list[chess.Move]) -> list[str]:
    """SAN for as many moves as are legal in sequence."""
    replay = board.copy(stack=False)
    sans = []
    for move in moves:
        if move not in replay.legal_moves:
            break
        sans.append(replay.san(move))
        replay.push(move)
    return sans


def analysis_lines(board: chess.Board, info: SearchInfo, elapsed: float) -> list[str]:
    parts = []
    if info.depth is not None:
        parts.append(f"depth {info.depth}")
    parts.append(f"nodes {info.nodes:,}")
    parts.append(f"{_rate(info.nodes, elapsed)} nodes/s")
    if info.score_cp is not None:
        parts.append(f"score {format_score(info.score_cp, board.turn == chess.WHITE)}")
    lines = ["  ".join(parts)]

    pv = _san_line(board, info.pv)
    if pv:
        lines.append("PV: " + " ".join(pv))

    for cand in info.candidates[:MAX_CANDIDATE_LINES]:
        san = _san_line(board, [cand.move])
        if not san:
            continue
        bits = [san[0]]
        if cand.visits is not None:
            share = f" ({cand.visits / info.nodes:.0%})" if info.nodes else ""
            bits.append(f"visits {cand.visits}{share}")
        if cand.value is not None:
            bits.append(f"win {cand.value:.0%}")
        if cand.score_cp is not None:
            bits.append(f"score {format_score(cand.score_cp, board.turn == chess.WHITE)}")
        lines.append("  ".join(bits))
    return lines


def candidate_arrows(info: SearchInfo, limit: int = 3) -> list[tuple[chess.Move, int]]:
    """Moves to draw as arrows, best first, with a width by rank."""
    if info.candidates:
        moves = [c.move for c in info.candidates[:limit]]
    elif info.pv:
        moves = info.pv[:1]
    else:
        return []
    return list(zip(moves, ARROW_WIDTHS))
