import random
import threading
import time

import chess
import pytest

from chessai.engines.base import (
    Candidate, SearchInfo, SearchLimit, SearchResult, allowed_time, engine_rng, run_search,
)

E2E4 = chess.Move.from_uci("e2e4")


class Fixed:
    name = "fixed"
    def __init__(self, answer=None, delay=0.0, exc=None):
        self.answer, self.delay, self.exc, self.seen = answer, delay, exc, None
    def search(self, board, limit, stop):
        self.seen = board
        board.push(chess.Move.from_uci("g1f3"))   # engines may mutate their copy
        time.sleep(self.delay)
        if self.exc:
            raise self.exc
        return self.answer


@pytest.mark.parametrize("kw", [{}, {"time_s": 0}, {"depth": -1}, {"iterations": 0}])
def test_limit_validation(kw):
    with pytest.raises(ValueError):
        SearchLimit(**kw)


def test_defaults_not_shared():
    assert SearchInfo().pv is not SearchInfo().pv
    assert SearchResult(E2E4).info.candidates == []


def test_engine_rng_independent_and_reproducible():
    assert engine_rng(1, "a").random() == engine_rng(1, "a").random()
    assert engine_rng(1, "a").random() != engine_rng(1, "b").random()
    assert engine_rng(1, "a").random() != random.Random(1).random()


def test_allowed_time():
    assert allowed_time(SearchLimit(time_s=1.0)) == pytest.approx(1.6)
    assert allowed_time(SearchLimit(depth=3)) is None


def test_ok_and_board_untouched():
    board = chess.Board()
    out = run_search(Fixed(SearchResult(E2E4)), board, SearchLimit(depth=1))
    assert out.ok and out.playable and out.result.move == E2E4 and out.problem is None
    assert board == chess.Board()          # caller's board unchanged


@pytest.mark.parametrize("answer", [None, SearchResult(chess.Move.from_uci("e2e5")), "e2e4"])
def test_illegal_or_wrong_type(answer):            # Review Focus 2
    out = run_search(Fixed(answer), chess.Board(), SearchLimit(depth=1))
    assert out.kind == "illegal" and out.result is None and not out.playable
    assert out.problem.startswith("illegal move")


def test_engine_exception():                          # Review Focus 2
    out = run_search(Fixed(exc=ValueError("boom")), chess.Board(), SearchLimit(depth=1))
    assert out.kind == "error" and out.problem == "engine error: ValueError: boom"


def test_overtime_keeps_move():
    out = run_search(Fixed(SearchResult(E2E4), delay=0.35), chess.Board(), SearchLimit(time_s=0.1))
    assert out.kind == "overtime" and out.playable and not out.ok
    assert out.result.move == E2E4 and "allowed" in out.problem


def test_game_over_board_rejected():
    mate = chess.Board("7k/6Q1/6K1/8/8/8/8/8 b - - 0 1")
    with pytest.raises(ValueError, match="game is already over"):
        run_search(Fixed(SearchResult(E2E4)), mate, SearchLimit(depth=1))


def test_stop_event_passed():
    stop = threading.Event()
    seen = {}
    class Spy(Fixed):
        def search(self, board, limit, s):
            seen["stop"] = s
            return SearchResult(E2E4)
    run_search(Spy(), chess.Board(), SearchLimit(depth=1), stop)
    assert seen["stop"] is stop


class Reports(Fixed):
    def __init__(self, info):
        super().__init__()
        self.info = info
    def search(self, board, limit, stop):
        return SearchResult(E2E4, self.info)


@pytest.mark.parametrize("info,check", [
    (None, lambda i: i == SearchInfo()),
    (SearchInfo(nodes=None), lambda i: i.nodes == 0),
    (SearchInfo(depth="5", score_cp="x"), lambda i: i.depth is None and i.score_cp is None),
    (SearchInfo(pv=["e2e4"]), lambda i: i.pv == []),
    (SearchInfo(pv=[E2E4, "e7e5"]), lambda i: i.pv == [E2E4]),
    (SearchInfo(candidates=["e2e4", Candidate(E2E4, visits="many"), Candidate(E2E4, visits=3)]),
     lambda i: i.candidates == [Candidate(E2E4, visits=3)]),
])
def test_bad_info_is_cleaned_not_fatal(info, check):        # final review #4
    out = run_search(Reports(info), chess.Board(), SearchLimit(depth=1))
    assert out.ok and out.result.move == E2E4
    assert isinstance(out.result.info, SearchInfo) and check(out.result.info)
    assert out.notes                                         # what was ignored is reported


def test_clean_info_has_no_notes():
    out = run_search(Reports(SearchInfo(nodes=5, pv=[E2E4])), chess.Board(), SearchLimit(depth=1))
    assert out.notes == ()
