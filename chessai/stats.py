"""Match and test statistics: score, Elo difference and confidence ranges."""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

ELO_CLAMP = 800.0   # a 0% or 100% score has no finite Elo; report it as beyond ±800
_EDGE = 1e-6


@dataclass(frozen=True)
class PairScore:
    """Engine A's results against B. `pair_points`: A's points in each opening pair (0–2)."""

    wins: int
    draws: int
    losses: int
    pair_points: tuple[float, ...]

    @property
    def games(self) -> int:
        return self.wins + self.draws + self.losses


def score(p: PairScore) -> float:
    return (p.wins + p.draws / 2) / p.games


def elo_from_score(s: float) -> float:
    """Elo difference that predicts expected score `s`, clamped to ±800."""
    if s <= _EDGE:
        return -ELO_CLAMP
    if s >= 1 - _EDGE:
        return ELO_CLAMP
    return max(-ELO_CLAMP, min(ELO_CLAMP, -400 * math.log10(1 / s - 1)))


def elo_interval(p: PairScore, z: float = 1.96) -> tuple[float, float]:
    """Confidence range for the Elo difference.

    The two games of an opening pair share a position, so they are not
    independent; the pairs are. The spread is measured over per-pair scores.
    """
    n = len(p.pair_points)
    if n < 2:
        return -ELO_CLAMP, ELO_CLAMP
    means = [points / 2 for points in p.pair_points]
    s = statistics.fmean(means)
    half = z * statistics.stdev(means) / math.sqrt(n)
    low, high = max(0.0, s - half), min(1.0, s + half)
    return elo_from_score(low), elo_from_score(high)


def format_elo(value: float) -> str:
    if value >= ELO_CLAMP:
        return f"> +{ELO_CLAMP:.0f}"
    if value <= -ELO_CLAMP:
        return f"< -{ELO_CLAMP:.0f}"
    return f"{round(value):+d}"


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a success rate (good near 0% and 100%)."""
    if n == 0:
        return 0.0, 1.0
    p = successes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)
