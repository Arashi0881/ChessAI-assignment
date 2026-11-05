import time

import chess
import pytest

import chessai.match.game as game_module
from chessai.engines import ENGINES
from chessai.engines.base import SearchInfo, SearchResult, allowed_time, SearchLimit
from chessai.match.game import HANG_GRACE_S, MAX_PLIES, GameSpec, play_game


class Scripted:
    """Plays the first legal move from a preference list, else the first legal move."""

    name = "scripted"
    prefer = ("g1f3", "g8f6", "f3g1", "f6g8")

    def __init__(self, rng):
        pass

    def search(self, board, limit, stop):
        legal = list(board.legal_moves)
        for uci in self.prefer:
            move = chess.Move.from_uci(uci)
            if move in legal:
                return SearchResult(move, SearchInfo(nodes=1, depth=1))
        return SearchResult(legal[0], SearchInfo(nodes=1))


class Illegal(Scripted):
    def search(self, board, limit, stop):
        return SearchResult(chess.Move.from_uci("a1a8"))


class Crash(Scripted):
    def search(self, board, limit, stop):
        raise RuntimeError("boom")


class Slow(Scripted):
    def search(self, board, limit, stop):
        time.sleep(0.3)
        return super().search(board, limit, stop)


class Hang(Scripted):
    def search(self, board, limit, stop):
        time.sleep(30)
        return super().search(board, limit, stop)


class BadInit:
    name = "badinit"

    def __init__(self, rng):
        raise RuntimeError("cannot build")


FAKES = {**ENGINES, "scripted": Scripted, "illegal": Illegal, "crash": Crash, "slow": Slow,
         "hang": Hang, "badinit": BadInit}


def spec(white, black, time_s=0.05, moves=(), seed=1, opening="Start"):
    return GameSpec(0, seed, white, black, time_s, opening, tuple(moves))


def movetext(pgn):
    return pgn.split("\n\n", 1)[1]


def test_greedy_beats_random():
    record = play_game(spec("greedy", "random", seed=1))
    assert record.result == "1-0"
    assert record.termination == "checkmate"
    assert 0 < record.plies <= MAX_PLIES
    assert record.white_stats.moves > 0 and record.black_stats.moves > 0
    assert record.white_stats.nodes > 0
    assert record.white_stats.depth_mean == 1


def test_reproducible():
    first = play_game(spec("greedy", "random", seed=5))
    second = play_game(spec("greedy", "random", seed=5))
    assert (first.result, first.plies) == (second.result, second.plies)
    assert movetext(first.pgn) == movetext(second.pgn)


def test_opening_applied():
    record = play_game(spec("greedy", "random", moves=("e2e4", "e7e5"), opening="Open Game"))
    assert movetext(record.pgn).startswith("1. e4 e5")
    assert '[Opening "Open Game"]' in record.pgn
    assert '[TimeControl "0.05 s/move"]' in record.pgn


@pytest.mark.parametrize("bad, kind", [("illegal", "illegal"), ("crash", "error"), ("slow", "overtime")])
def test_faulty_engine_forfeits(bad, kind):
    record = play_game(spec("scripted", bad), FAKES)
    assert record.result == "1-0"
    assert record.termination == f"forfeit: {kind} (black)"
    record = play_game(spec(bad, "scripted"), FAKES)
    assert record.result == "0-1"
    assert record.termination == f"forfeit: {kind} (white)"
    assert f'[Termination "forfeit: {kind} (white)"]' in record.pgn


def test_hung_engine_forfeits():
    start = time.perf_counter()
    record = play_game(spec("hang", "scripted"), FAKES)
    took = time.perf_counter() - start
    assert record.result == "0-1"
    assert record.termination == "forfeit: no answer (white)"
    assert took < allowed_time(SearchLimit(time_s=0.05)) + HANG_GRACE_S + 1


def test_threefold_claimed():
    record = play_game(spec("scripted", "scripted"), FAKES)
    assert record.result == "1/2-1/2"
    assert record.termination == "threefold repetition"
    # FIDE 9.2: the player to move may claim before making the move that repeats
    assert record.plies == 7


def test_move_limit(monkeypatch):
    monkeypatch.setattr(game_module, "MAX_PLIES", 6)
    record = play_game(spec("random", "random", seed=3))
    assert record.result == "1/2-1/2"
    assert record.termination == "move limit"
    assert record.plies == 6
    assert '[Result "1/2-1/2"]' in record.pgn


def test_constructor_error_forfeits():
    record = play_game(spec("scripted", "badinit"), FAKES)
    assert record.result == "1-0"
    assert record.termination == "forfeit: error (black)"
    assert record.plies == 0


class SysExit(Scripted):
    def search(self, board, limit, stop):
        raise SystemExit("debug exit left in the engine")


def test_sys_exit_in_engine_forfeits():                     # final review #3
    record = play_game(spec("scripted", "sysexit"), {**FAKES, "sysexit": SysExit})
    assert record.result == "1-0"
    assert record.termination == "forfeit: error (black)"
