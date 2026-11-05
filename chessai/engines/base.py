"""The engine contract shared by the GUI and every tool.

An engine receives a copy of the board, a SearchLimit and a stop event, and
returns a SearchResult. `run_search` is the only way the rest of the program
calls an engine: it checks the answer, so a buggy engine can never play an
illegal move or crash the caller.
"""
from __future__ import annotations

import numbers
import random
import threading
import time
from dataclasses import dataclass, field
from typing import ClassVar, Literal, Protocol

import chess

OVERTIME_FACTOR = 1.5   # a search may use up to 1.5 × its time budget …
OVERTIME_GRACE_S = 0.1  # … plus this many seconds before it counts as overtime


@dataclass(frozen=True)
class SearchLimit:
    """How long an engine may think. At least one field must be set."""

    time_s: float | None = None        # wall-clock budget for this move
    depth: int | None = None           # alpha-beta style limit
    iterations: int | None = None      # MCTS style limit

    def __post_init__(self) -> None:
        values = (self.time_s, self.depth, self.iterations)
        if all(v is None for v in values):
            raise ValueError("SearchLimit needs time_s, depth or iterations")
        for name, value in zip(("time_s", "depth", "iterations"), values):
            if value is not None and value <= 0:
                raise ValueError(f"{name} must be positive, got {value}")


@dataclass(frozen=True)
class Candidate:
    """A move the engine considered, with whatever it knows about it."""

    move: chess.Move
    visits: int | None = None      # MCTS: how often it was explored
    value: float | None = None     # MCTS: win rate in [0, 1] for the side to move
    score_cp: int | None = None    # alpha-beta: score in centipawns, side to move


@dataclass
class SearchInfo:
    """What an engine reports about its search. Every field is optional."""

    nodes: int = 0                 # positions visited (alpha-beta) or simulations (MCTS)
    depth: int | None = None       # deepest completed iteration
    score_cp: int | None = None    # evaluation in centipawns, from the side to move's view
    pv: list[chess.Move] = field(default_factory=list)            # principal variation
    candidates: list[Candidate] = field(default_factory=list)     # best moves first


@dataclass(frozen=True)
class SearchResult:
    move: chess.Move
    info: SearchInfo = field(default_factory=SearchInfo)


class Engine(Protocol):
    name: ClassVar[str]

    def __init__(self, rng: random.Random) -> None: ...

    def search(
        self, board: chess.Board, limit: SearchLimit, stop: threading.Event
    ) -> SearchResult: ...


def engine_rng(seed: int, name: str) -> random.Random:
    """Reproducible RNG for one engine, independent of every other random stream."""
    return random.Random(f"engine:{name}:{seed}")


def allowed_time(limit: SearchLimit) -> float | None:
    """Seconds a search may take before it counts as overtime (None: no time limit)."""
    if limit.time_s is None:
        return None
    return limit.time_s * OVERTIME_FACTOR + OVERTIME_GRACE_S


@dataclass(frozen=True)
class SearchOutcome:
    result: SearchResult | None
    elapsed: float
    problem: str | None
    kind: Literal["ok", "overtime", "illegal", "error"]
    notes: tuple[str, ...] = ()   # parts of the engine's SearchInfo that were ignored

    @property
    def ok(self) -> bool:
        return self.kind == "ok"

    @property
    def playable(self) -> bool:
        """True when the move may be played (overtime moves are legal, just late)."""
        return self.kind in ("ok", "overtime")


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: object) -> bool:
    return isinstance(value, numbers.Real) and not isinstance(value, bool)


def _valid_candidate(c: object) -> bool:
    return (
        isinstance(c, Candidate)
        and isinstance(c.move, chess.Move)
        and (c.visits is None or _is_int(c.visits))
        and (c.value is None or _is_number(c.value))
        and (c.score_cp is None or _is_int(c.score_cp))
    )


def clean_info(info: object) -> tuple[SearchInfo, tuple[str, ...]]:
    """A SearchInfo safe to display, plus notes on anything that had to be dropped.

    Engines are student code: a wrong type in the report must never break the
    GUI or a match, but it should be visible.
    """
    if not isinstance(info, SearchInfo):
        return SearchInfo(), (f"info ignored: expected SearchInfo, got {type(info).__name__}",)
    notes = []
    nodes = info.nodes if _is_int(info.nodes) else 0
    if nodes != info.nodes:
        notes.append(f"nodes ignored: {info.nodes!r}")
    depth = info.depth if info.depth is None or _is_int(info.depth) else None
    if depth != info.depth:
        notes.append(f"depth ignored: {info.depth!r}")
    score = info.score_cp if info.score_cp is None or _is_int(info.score_cp) else None
    if score != info.score_cp:
        notes.append(f"score_cp ignored: {info.score_cp!r}")
    pv = []
    for move in info.pv if isinstance(info.pv, list) else []:
        if not isinstance(move, chess.Move):
            break
        pv.append(move)
    if not isinstance(info.pv, list) or len(pv) != len(info.pv):
        notes.append("pv cut at the first entry that is not a chess.Move")
    raw = info.candidates if isinstance(info.candidates, list) else []
    candidates = [c for c in raw if _valid_candidate(c)]
    if not isinstance(info.candidates, list) or len(candidates) != len(info.candidates):
        notes.append("candidates with wrong types ignored")
    return SearchInfo(nodes, depth, score, pv, candidates), tuple(notes)


def run_search(
    engine: Engine,
    board: chess.Board,
    limit: SearchLimit,
    stop: threading.Event | None = None,
) -> SearchOutcome:
    """Ask `engine` for a move on a copy of `board` and check its answer."""
    if board.is_game_over():
        raise ValueError("game is already over")
    stop = stop if stop is not None else threading.Event()
    start = time.perf_counter()
    try:
        answer = engine.search(board.copy(), limit, stop)
    except Exception as exc:  # an engine bug must not crash the GUI or a match
        elapsed = time.perf_counter() - start
        return SearchOutcome(None, elapsed, f"engine error: {type(exc).__name__}: {exc}", "error")
    elapsed = time.perf_counter() - start

    if not isinstance(answer, SearchResult) or not isinstance(answer.move, chess.Move):
        shown = getattr(answer, "move", answer)
        return SearchOutcome(None, elapsed, f"illegal move: {shown!r}", "illegal")
    if answer.move not in board.legal_moves:
        return SearchOutcome(None, elapsed, f"illegal move: {answer.move.uci()}", "illegal")

    info, notes = clean_info(answer.info)
    answer = SearchResult(answer.move, info)
    budget = allowed_time(limit)
    if budget is not None and elapsed > budget:
        problem = f"overtime: {elapsed:.2f} s > {budget:.2f} s allowed"
        return SearchOutcome(answer, elapsed, problem, "overtime", notes)
    return SearchOutcome(answer, elapsed, None, "ok", notes)
