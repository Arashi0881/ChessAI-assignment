"""Fake engines that spawned match workers can import (see test_hang_in_worker_process)."""
import time

from chessai.engines import ENGINES
from chessai.engines.base import SearchResult


class HangEngine:
    name = "hang-test"

    def __init__(self, rng):
        pass

    def search(self, board, limit, stop):
        time.sleep(30)
        return SearchResult(next(iter(board.legal_moves)))


ENGINES[HangEngine.name] = HangEngine


class ExitEngine:
    """Kills its own process, like an out-of-memory kill or a crash in C code."""

    name = "exit-test"

    def __init__(self, rng):
        pass

    def search(self, board, limit, stop):
        import os
        os._exit(3)


ENGINES[ExitEngine.name] = ExitEngine
