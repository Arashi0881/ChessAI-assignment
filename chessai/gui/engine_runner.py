"""Run an engine search off the Tk thread (no tkinter here; unit-tested).

The worker only computes and puts a RunnerResult on a queue; the GUI polls
from the Tk thread. Python cannot kill a thread, so `cancel` sets the job's
stop event (a well-behaved engine then returns quickly) and ignores whatever
the job eventually returns. `stop` also sets the event but keeps the answer:
that is the "move now" button.
"""
from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass

import chess

from chessai.engines.base import SearchLimit, SearchOutcome, run_search


@dataclass(frozen=True)
class RunnerResult:
    job: int
    outcome: SearchOutcome


class EngineRunner:
    def __init__(self) -> None:
        self._results: queue.Queue[RunnerResult] = queue.Queue()
        self._job = 0
        self._busy = False
        self._started = 0.0
        self._stop: threading.Event | None = None
        self._thread: threading.Thread | None = None
        self._abandoned: list[threading.Thread] = []

    @property
    def busy(self) -> bool:
        return self._busy

    @property
    def zombies(self) -> int:
        """Cancelled searches whose threads are still running (engines ignoring stop)."""
        self._abandoned = [t for t in self._abandoned if t.is_alive()]
        return len(self._abandoned)

    @property
    def elapsed(self) -> float:
        return time.perf_counter() - self._started if self._busy else 0.0

    def start(self, engine, board: chess.Board, limit: SearchLimit) -> int:
        """Search a copy of `board` in the background. Supersedes any running job."""
        if self._busy:
            self.cancel()
        self._job += 1
        job = self._job
        self._stop = threading.Event()
        self._busy = True
        self._started = time.perf_counter()
        self._thread = threading.Thread(
            target=self._work,
            args=(job, engine, board.copy(), limit, self._stop),
            name=f"engine-{job}",
            daemon=True,  # a runaway engine never keeps the program alive
        )
        self._thread.start()
        return job

    def stop(self) -> None:
        """Ask the engine to finish now; its answer is still delivered."""
        if self._busy and self._stop is not None:
            self._stop.set()

    def cancel(self) -> None:
        """Ask the engine to finish and ignore its answer."""
        if self._stop is not None:
            self._stop.set()
        if self._busy and self._thread is not None and self._thread.is_alive():
            self._abandoned.append(self._thread)
        self._job += 1
        self._busy = False

    def poll(self) -> RunnerResult | None:
        """The current job's result, once; None while running or when idle."""
        while True:
            try:
                result = self._results.get_nowait()
            except queue.Empty:
                return None
            if self._busy and result.job == self._job:
                self._busy = False
                return result
            # a cancelled or superseded job: drop it

    def _work(self, job: int, engine, board: chess.Board, limit: SearchLimit, stop: threading.Event) -> None:
        start = time.perf_counter()
        try:
            outcome = run_search(engine, board, limit, stop)
        except BaseException as exc:  # never let a worker die silently
            outcome = SearchOutcome(
                None, time.perf_counter() - start,
                f"engine error: {type(exc).__name__}: {exc}", "error",
            )
        self._results.put(RunnerResult(job, outcome))
