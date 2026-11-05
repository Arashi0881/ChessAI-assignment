import threading
import time

import chess
import pytest

from chessai.engines.base import SearchLimit, SearchResult
from chessai.gui.engine_runner import EngineRunner

E2E4 = chess.Move.from_uci("e2e4")
D2D4 = chess.Move.from_uci("d2d4")
LIMIT = SearchLimit(time_s=5.0)
MATE = "7k/6Q1/6K1/8/8/8/8/8 b - - 0 1"


class Instant:
    name = "instant"
    def search(self, board, limit, stop):
        return SearchResult(E2E4)


class Gated:
    """Blocks until released; records the board it was given."""
    name = "gated"
    def __init__(self, move=E2E4):
        self.started, self.release, self.move, self.seen = threading.Event(), threading.Event(), move, None
        self.stop = None
    def search(self, board, limit, stop):
        self.stop = stop
        self.started.set()
        self.release.wait(5)
        self.seen = board.fen()
        return SearchResult(self.move)


class UntilStopped:
    name = "until-stopped"
    def search(self, board, limit, stop):
        stop.wait(5)
        return SearchResult(D2D4)


class Runaway:
    name = "runaway"
    def __init__(self):
        self.started = threading.Event()
    def search(self, board, limit, stop):
        self.started.set()
        time.sleep(5)              # ignores stop entirely
        return SearchResult(E2E4)


def wait_result(runner, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = runner.poll()
        if result is not None:
            return result
        time.sleep(0.005)
    pytest.fail("no result within timeout")


def test_idle():
    r = EngineRunner()
    assert not r.busy and r.elapsed == 0.0 and r.poll() is None


def test_result_delivered_once():
    r = EngineRunner()
    job = r.start(Instant(), chess.Board(), LIMIT)
    res = wait_result(r)
    assert res.job == job and res.outcome.ok and res.outcome.result.move == E2E4
    assert not r.busy and r.poll() is None


def test_board_copied_at_start():
    r = EngineRunner()
    board, engine = chess.Board(), Gated()
    r.start(engine, board, LIMIT)
    assert engine.started.wait(2)
    board.push(E2E4)                       # caller keeps playing on its own board
    engine.release.set()
    wait_result(r)
    assert engine.seen == chess.STARTING_FEN


def test_stop_delivers_best_so_far():
    r = EngineRunner()
    r.start(UntilStopped(), chess.Board(), LIMIT)
    time.sleep(0.05)
    assert r.busy and r.poll() is None
    r.stop()
    assert wait_result(r).outcome.result.move == D2D4


def test_cancel_drops_result():               # Review Focus 4
    r = EngineRunner()
    engine = Gated()
    r.start(engine, chess.Board(), LIMIT)
    assert engine.started.wait(2)
    r.cancel()
    assert engine.stop.is_set()
    assert not r.busy and r.elapsed == 0.0
    engine.release.set()
    time.sleep(0.1)
    assert r.poll() is None


def test_restart_supersedes():
    r = EngineRunner()
    first = Gated()
    r.start(first, chess.Board(), LIMIT)
    assert first.started.wait(2)
    second = r.start(Instant(), chess.Board(), LIMIT)
    assert first.stop.is_set()
    first.release.set()
    res = wait_result(r)
    assert res.job == second
    time.sleep(0.1)
    assert r.poll() is None


def test_runaway_engine_is_daemon():          # Review Focus 5
    r = EngineRunner()
    engine = Runaway()
    job = r.start(engine, chess.Board(), LIMIT)
    assert engine.started.wait(2)
    worker = next(t for t in threading.enumerate() if t.name == f"engine-{job}")
    assert worker.daemon
    t0 = time.monotonic()
    r.cancel()
    assert time.monotonic() - t0 < 0.1 and not r.busy


def test_game_over_board_becomes_error():
    r = EngineRunner()
    r.start(Instant(), chess.Board(MATE), LIMIT)
    out = wait_result(r).outcome
    assert out.kind == "error" and "game is already over" in out.problem


def test_zombie_threads_counted():                          # final review #6
    r = EngineRunner()
    engines = [Runaway(), Runaway()]
    for engine in engines:
        r.start(engine, chess.Board(), LIMIT)
        assert engine.started.wait(2)
        r.cancel()
    assert r.zombies == 2
    assert EngineRunner().zombies == 0
