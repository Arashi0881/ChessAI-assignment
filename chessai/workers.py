"""Run tasks (games, puzzles) each in a fresh process, surviving engines that hang or die.

Every task gets its own "spawn" process (the same on every OS), so:
- a hung engine thread is killed with its process instead of eating CPU later;
- an engine that kills its process (out of memory, os._exit, a crash in C
  code) turns into a "crash" result for that one task instead of a hang;
- one task's engine state cannot leak into the next.
"""
from __future__ import annotations

import importlib
import multiprocessing
import os
import signal
from collections.abc import Callable, Sequence
from multiprocessing.connection import wait
from typing import Any

# Shared progress markers a task updates so a crash can be blamed: [side, step].
UNKNOWN = -1


def _child(fn: Callable, task: Any, conn, state, engine_module: str | None) -> None:
    signal.signal(signal.SIGINT, signal.SIG_IGN)   # Ctrl+C is handled by the parent
    if engine_module:
        importlib.import_module(engine_module)       # registers extra engines into ENGINES
    conn.send(fn(task, state))
    conn.close()


def run_tasks(fn: Callable[[Any, Any], Any], tasks: Sequence[Any], jobs: int,
              on_crash: Callable[[Any, tuple[int, int]], Any],
              progress: Callable[[Any], None] | None = None,
              engine_module: str | None = None) -> list:
    """`fn(task, state)` for every task, at most `jobs` at a time; results in task order.

    `progress` sees each result as it finishes (finishing order). If a process
    dies without answering, `on_crash(task, (side, step))` makes its result.
    On Ctrl+C every running process is stopped and KeyboardInterrupt re-raised.
    """
    context = multiprocessing.get_context("spawn")
    results: list = [None] * len(tasks)
    waiting = list(range(len(tasks)))[::-1]
    running: dict[int, tuple] = {}   # index -> (process, connection, state)
    try:
        while waiting or running:
            while waiting and len(running) < max(1, jobs):
                i = waiting.pop()
                receive, send = context.Pipe(duplex=False)
                state = context.Array("i", [UNKNOWN, 0])
                process = context.Process(target=_child, args=(fn, tasks[i], send, state, engine_module),
                                          daemon=True)
                process.start()
                send.close()
                running[i] = (process, receive, state)
            ready = wait([conn for _, conn, _ in running.values()])
            for i in [i for i, (_, conn, _) in running.items() if conn in ready]:
                process, conn, state = running.pop(i)
                try:
                    results[i] = conn.recv()
                except EOFError:              # the process died without answering
                    results[i] = on_crash(tasks[i], (state[0], state[1]))
                conn.close()
                process.join()
                if progress:
                    progress(results[i])
    finally:
        for process, conn, _ in running.values():
            process.terminate()
            conn.close()
        for process, _, _ in running.values():
            process.join()
    return results


def default_jobs() -> int:
    """Half the logical CPUs (about one per physical core): each game gets a whole core."""
    return max(1, (os.cpu_count() or 2) // 2)
