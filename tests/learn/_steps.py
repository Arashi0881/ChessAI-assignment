"""Helpers for the step tests: skip unwritten steps, and a fixed evaluation for fixtures."""
from __future__ import annotations

import functools
import json
from collections.abc import Callable
from pathlib import Path

import chess
import pytest

from chessai.engines.baselines import material

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def step(tutorial: str):
    """Turn NotImplementedError (a stub not written yet) into a skip naming the tutorial."""
    def decorate(test):
        @functools.wraps(test)
        def run(*args, **kwargs):
            try:
                return test(*args, **kwargs)
            except NotImplementedError:
                pytest.skip(f"not written yet: read {tutorial}")
        return run
    return decorate


def fixture_eval(board: chess.Board) -> int:
    """The evaluation the fixtures were made with: material 1/3/3/5/9 × 100, side to move.

    Step tests pass this to your search so its result can be compared with
    the stored values, whatever your own evaluate() does.
    """
    return (material(board, board.turn) - material(board, not board.turn)) * 100


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def counting(evaluate: Callable[[chess.Board], int]) -> tuple[Callable[[chess.Board], int], list[int]]:
    """Wrap an evaluation to count calls; the count is in calls[0]."""
    calls = [0]

    def counted(board: chess.Board) -> int:
        calls[0] += 1
        return evaluate(board)

    return counted, calls


def run_engine(engine, board: chess.Board, limit, stop=None):
    """run_search, but an engine that is still a stub counts as 'not written yet'."""
    from chessai.engines.base import run_search
    outcome = run_search(engine, board, limit, stop)
    if outcome.problem and "NotImplementedError" in outcome.problem:
        raise NotImplementedError(outcome.problem)
    return outcome
