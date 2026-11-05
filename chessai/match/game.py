"""Play one engine-vs-engine game with match rules: forfeits, claimed draws, a move limit."""
from __future__ import annotations

import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass, field

import chess
import chess.pgn

from chessai.engines import ENGINES
from chessai.engines.base import SearchLimit, SearchOutcome, allowed_time, engine_rng, run_search

HANG_GRACE_S = 2.0   # seconds past the allowed time before a silent engine forfeits
MAX_PLIES = 300      # plies after the opening; then the game is adjudicated a draw

_REASONS = {
    chess.Termination.CHECKMATE: "checkmate",
    chess.Termination.STALEMATE: "stalemate",
    chess.Termination.INSUFFICIENT_MATERIAL: "insufficient material",
    chess.Termination.SEVENTYFIVE_MOVES: "75-move rule",
    chess.Termination.FIVEFOLD_REPETITION: "fivefold repetition",
    chess.Termination.FIFTY_MOVES: "50-move rule",
    chess.Termination.THREEFOLD_REPETITION: "threefold repetition",
}


@dataclass(frozen=True)
class GameSpec:
    index: int
    seed: int
    white: str
    black: str
    time_s: float
    opening: str
    opening_moves: tuple[str, ...]   # UCI, so a spec pickles cheaply into worker processes


@dataclass
class SideStats:
    moves: int = 0
    time_total: float = 0.0
    time_max: float = 0.0
    nodes: int = 0
    depth_total: int = 0
    depth_count: int = 0      # moves that reported a depth

    @property
    def time_mean(self) -> float:
        return self.time_total / self.moves if self.moves else 0.0

    @property
    def nps(self) -> float:
        return self.nodes / self.time_total if self.time_total > 0 else 0.0

    @property
    def depth_mean(self) -> float | None:
        return self.depth_total / self.depth_count if self.depth_count else None

    def add(self, outcome: SearchOutcome) -> None:
        self.moves += 1
        self.time_total += outcome.elapsed
        self.time_max = max(self.time_max, outcome.elapsed)
        info = outcome.result.info
        self.nodes += info.nodes
        if info.depth is not None:
            self.depth_total += info.depth
            self.depth_count += 1


@dataclass(frozen=True)
class GameRecord:
    index: int
    seed: int
    white: str
    black: str
    time_s: float
    opening: str
    white_eval: str      # each engine's `evaluation` attribute: what was held constant
    black_eval: str
    result: str          # "1-0", "0-1" or "1/2-1/2"
    termination: str     # e.g. "checkmate", "move limit", "forfeit: illegal (white)"
    plies: int           # plies played after the opening
    white_stats: SideStats = field(default_factory=SideStats)
    black_stats: SideStats = field(default_factory=SideStats)
    pgn: str = ""


def guarded_search(engine, board: chess.Board, limit: SearchLimit) -> SearchOutcome | None:
    """run_search on a daemon thread; None if the engine has not answered in time.

    A hung thread cannot be killed; it is abandoned (in a match worker process,
    it dies with the process).
    """
    box: list[SearchOutcome] = []
    stop = threading.Event()
    start = time.perf_counter()

    def target() -> None:
        try:
            box.append(run_search(engine, board, limit, stop))
        except BaseException as exc:   # sys.exit() left in an engine must not end the run
            box.append(SearchOutcome(None, time.perf_counter() - start,
                                     f"engine error: {type(exc).__name__}: {exc}", "error"))

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    budget = allowed_time(limit)
    thread.join(None if budget is None else budget + HANG_GRACE_S)
    if thread.is_alive():
        stop.set()
        return None
    return box[0]


def _forfeit(color: chess.Color, kind: str) -> tuple[str, str]:
    side = "white" if color == chess.WHITE else "black"
    return ("0-1" if color == chess.WHITE else "1-0"), f"forfeit: {kind} ({side})"


def _opening_board(spec: GameSpec) -> chess.Board:
    board = chess.Board()
    for uci in spec.opening_moves:
        board.push(chess.Move.from_uci(uci))
    return board


def _pgn(spec: GameSpec, board: chess.Board, result: str, termination: str) -> str:
    game = chess.pgn.Game.from_board(board)
    game.headers["Event"] = "chessai match"
    game.headers["White"] = spec.white
    game.headers["Black"] = spec.black
    game.headers["Result"] = result
    game.headers["Opening"] = spec.opening
    game.headers["Termination"] = termination
    game.headers["TimeControl"] = f"{spec.time_s:g} s/move"
    game.headers["Seed"] = str(spec.seed)
    return str(game)


def _evaluations(spec: GameSpec, engines: Mapping[str, type] = ENGINES) -> tuple[str, str]:
    return tuple(str(getattr(engines.get(name), "evaluation", "")) for name in (spec.white, spec.black))


def crash_record(spec: GameSpec, marks: tuple[int, int]) -> GameRecord:
    """The record of a game whose process died; `marks` = (side that was thinking, plies)."""
    color = chess.WHITE if marks[0] != chess.BLACK else chess.BLACK
    result, termination = _forfeit(color, "crash")
    pgn = _pgn(spec, _opening_board(spec), result, termination)   # the moves died with the process
    return GameRecord(spec.index, spec.seed, spec.white, spec.black, spec.time_s, spec.opening,
                      *_evaluations(spec), result, termination, max(0, marks[1]), SideStats(), SideStats(), pgn)


def play_game(spec: GameSpec, engines: Mapping[str, type] = ENGINES, state=None) -> GameRecord:
    """Play one game. `state`, if given, is set to [side to move, plies] before each
    engine call, so that if the process dies the parent knows whom to blame."""
    board = _opening_board(spec)
    limit = SearchLimit(time_s=spec.time_s)
    names = {chess.WHITE: spec.white, chess.BLACK: spec.black}
    stats = {chess.WHITE: SideStats(), chess.BLACK: SideStats()}
    result = termination = None

    players = {}
    for color, name in names.items():
        if state is not None:
            state[0] = int(color)
        try:
            players[color] = engines[name](engine_rng(spec.seed, f"{name}:{'white' if color else 'black'}"))
        except Exception:
            result, termination = _forfeit(color, "error")
            break

    plies = 0
    while result is None:
        outcome = board.outcome(claim_draw=True)
        if outcome is not None:
            result, termination = outcome.result(), _REASONS[outcome.termination]
            break
        if plies >= MAX_PLIES:
            result, termination = "1/2-1/2", "move limit"
            break
        mover = board.turn
        if state is not None:
            state[0], state[1] = int(mover), plies
        answer = guarded_search(players[mover], board, limit)
        if answer is None:
            result, termination = _forfeit(mover, "no answer")
            break
        if not answer.ok:
            result, termination = _forfeit(mover, answer.kind)
            break
        stats[mover].add(answer)
        board.push(answer.result.move)
        plies += 1

    return GameRecord(spec.index, spec.seed, spec.white, spec.black, spec.time_s, spec.opening,
                      *_evaluations(spec, engines), result, termination, plies, stats[chess.WHITE], stats[chess.BLACK],
                      _pgn(spec, board, result, termination))
