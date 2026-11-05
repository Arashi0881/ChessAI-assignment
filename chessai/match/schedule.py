"""A fair schedule of games, and running it in worker processes."""
from __future__ import annotations

import itertools
import random
from collections.abc import Callable, Sequence

from chessai.data import Opening
from chessai.match.game import GameRecord, GameSpec, crash_record, play_game
from chessai.stats import PairScore
from chessai.workers import run_tasks

SEED_STRIDE = 1_000_003


def build_schedule(engines: list[str], times: list[float], games: int,
                   openings: list[Opening], seed: int) -> list[GameSpec]:
    """Every engine pair at every time; each opening played twice with colours swapped."""
    if games <= 0 or games % 2:
        raise ValueError(f"--games must be a positive even number (each opening is played twice), got {games}")
    if games > 2 * len(openings):
        raise ValueError(f"{games} games per pair need {games // 2} distinct openings, "
                         f"only {len(openings)} openings available")
    specs = []
    for a, b in itertools.combinations(engines, 2):
        for t in times:
            chosen = list(openings)
            random.Random(f"openings:{seed}:{a}:{b}:{t}").shuffle(chosen)
            for opening in chosen[: games // 2]:
                moves = tuple(move.uci() for move in opening.moves)
                for white, black in ((a, b), (b, a)):
                    index = len(specs)
                    specs.append(GameSpec(index, seed * SEED_STRIDE + index, white, black, t,
                                          opening.name, moves))
    return specs


def _play(spec: GameSpec, state) -> GameRecord:
    return play_game(spec, state=state)


def run_schedule(specs: Sequence[GameSpec], jobs: int,
                 progress: Callable[[GameRecord], None] | None = None,
                 engine_module: str | None = None) -> list[GameRecord]:
    """Play every game, each in a fresh process; results in schedule order, the same for any `jobs`.

    `progress` sees each game as it finishes. A game whose process dies is a
    forfeit "crash" for the side that was thinking (see chessai.workers).
    """
    return run_tasks(_play, specs, jobs, crash_record, progress, engine_module)


def summarize(records: Sequence[GameRecord], a: str, b: str, time_s: float) -> PairScore:
    """A's results against B at one time per move, grouped into opening pairs."""
    wins = draws = losses = 0
    pairs: dict[str, float] = {}
    played: dict[str, int] = {}
    for r in records:
        if r.time_s != time_s or {r.white, r.black} != {a, b}:
            continue
        a_white = r.white == a
        if r.result == "1/2-1/2":
            draws += 1
            points = 0.5
        elif (r.result == "1-0") == a_white:
            wins += 1
            points = 1.0
        else:
            losses += 1
            points = 0.0
        pairs[r.opening] = pairs.get(r.opening, 0.0) + points
        played[r.opening] = played.get(r.opening, 0) + 1
    # only complete pairs feed the confidence range (an interrupted run can leave half a pair)
    return PairScore(wins, draws, losses, tuple(p for name, p in pairs.items() if played[name] == 2))
