import threading
import chess
from chessai.engines import ENGINES
from chessai.engines.base import SearchLimit, engine_rng, run_search
from chessai.engines.baselines import GreedyEngine, RandomEngine, material

LIMIT = SearchLimit(time_s=1.0)


def play(engine_cls, fen, seed=0):
    return run_search(engine_cls(engine_rng(seed, engine_cls.name)), chess.Board(fen), LIMIT)


def test_registry():
    assert ENGINES["random"] is RandomEngine
    assert ENGINES["greedy"] is GreedyEngine


def test_material():
    b = chess.Board()
    assert material(b, chess.WHITE) == material(b, chess.BLACK) == 39


def test_random_is_legal_and_reproducible():
    moves = {play(RandomEngine, chess.STARTING_FEN, seed=5).result.move for _ in range(3)}
    assert len(moves) == 1
    many = {play(RandomEngine, chess.STARTING_FEN, seed=s).result.move for s in range(40)}
    assert len(many) > 5


def test_greedy_takes_free_queen():
    fen = "4k3/8/8/3q4/4P3/8/8/4K3 w - - 0 1"      # exd5 wins the queen
    out = play(GreedyEngine, fen)
    assert out.ok and out.result.move == chess.Move.from_uci("e4d5")
    # balance after the capture: +1 pawn for White
    assert out.result.info.score_cp == 100
    assert out.result.info.candidates[0].move == out.result.move


def test_greedy_prefers_mate():
    out = play(GreedyEngine, "6k1/5ppp/8/8/8/8/8/R3K3 w - - 0 1")   # Ra8#
    assert out.result.move == chess.Move.from_uci("a1a8")


def test_greedy_ties_broken_by_rng():
    picks = {play(GreedyEngine, chess.STARTING_FEN, seed=s).result.move for s in range(30)}
    assert len(picks) > 3
