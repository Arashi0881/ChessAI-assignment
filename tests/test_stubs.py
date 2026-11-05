"""The engine stubs the team fills in: they must be safe to ship unfinished."""
import random
import subprocess
import sys
import threading
from pathlib import Path

import chess
import pytest

from chessai.engines import ENGINES, SearchLimit, engine_rng, run_search
from chessai.engines import alphabeta, evaluate, mcts
from chessai.match.game import GameSpec, play_game
from tests.learn._steps import counting, fixture_eval, step

START = chess.Board()


def test_registry_order():
    assert list(ENGINES) == ["random", "greedy", "minimax", "alphabeta", "mcts"]


def unwritten(call) -> bool:
    """True while the team has not written this piece yet."""
    try:
        call()
    except NotImplementedError:
        return True
    except Exception:
        return False
    return False


def test_stub_modules_ship_unwritten_or_working():
    """Shipped stubs raise NotImplementedError; nothing else may break on import or call."""
    assert alphabeta.INFINITY > evaluate.MATE_SCORE * 2
    assert isinstance(evaluate.EVAL_NAME, str) and isinstance(evaluate.EVAL_VERSION, int)
    assert issubclass(alphabeta.SearchTimeout, Exception)


@pytest.mark.parametrize("name", ["minimax", "alphabeta", "mcts"])
def test_engines_construct_and_never_crash_the_caller(name):
    engine = ENGINES[name](engine_rng(0, name))
    outcome = run_search(engine, START, SearchLimit(time_s=0.2, depth=2, iterations=200), threading.Event())
    assert outcome.kind in ("ok", "overtime") or "NotImplementedError" in outcome.problem, outcome.problem
    assert ENGINES[name].evaluation == f"{evaluate.EVAL_NAME} v{evaluate.EVAL_VERSION}"


def test_unwritten_engine_forfeits_a_match():
    if not unwritten(lambda: alphabeta.AlphaBetaEngine(random.Random(0)).search(
            START.copy(), SearchLimit(depth=1), threading.Event())):
        pytest.skip("alphabeta is written; tests/learn checks it")
    record = play_game(GameSpec(0, 1, "alphabeta", "greedy", 0.05, "Start", ()))
    assert record.termination == "forfeit: error (white)"
    assert record.white_eval == alphabeta.AlphaBetaEngine.evaluation   # tracks EVAL_NAME / EVAL_VERSION
    assert record.black_eval == "material 1/3/3/5/9"


def test_node_root():
    root = mcts.Node.root(chess.Board())
    assert len(root.untried) == 20
    assert root.children == [] and root.visits == 0 and root.value_sum == 0.0
    assert root.move is None and root.parent is None


def test_step_decorator():
    @step("docs/learn/01-minimax.md")
    def unwritten():
        raise NotImplementedError

    @step("docs/learn/01-minimax.md")
    def wrong():
        assert False

    with pytest.raises(pytest.skip.Exception, match="docs/learn/01-minimax.md"):
        unwritten()
    with pytest.raises(AssertionError):
        wrong()
    assert unwritten.__name__ == "unwritten"


def test_helpers():
    assert fixture_eval(chess.Board()) == 0
    board = chess.Board("rnbqkb1r/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")   # black knight missing
    assert fixture_eval(board) == 300
    board.turn = chess.BLACK
    assert fixture_eval(board) == -300
    counted, calls = counting(fixture_eval)
    counted(board)
    counted(board)
    assert calls == [2]


TEAM_FUNCTIONS = [
    lambda: evaluate.material(START.copy()),
    lambda: alphabeta.negamax(START.copy(), 0, fixture_eval),
    lambda: alphabeta.order_moves(START.copy()),
    lambda: mcts.uct_score(1.0, 2, 3, 1.4),
    lambda: mcts.cp_to_win(0),
]


def test_stubs_skip_cleanly():                          # Review Focus 1
    if not all(unwritten(call) for call in TEAM_FUNCTIONS):
        pytest.skip("the team's code is in; tests/learn reports on it directly")
    root = Path(__file__).resolve().parents[1]
    done = subprocess.run([sys.executable, "-m", "pytest", "tests/learn", "-q", "-rs", "-p", "no:cacheprovider"],
                          capture_output=True, text=True, cwd=root)
    assert done.returncode in (0, 5), done.stdout[-2000:]
    tail = done.stdout.lower()
    assert " failed" not in tail and " error" not in tail, done.stdout[-2000:]
    skips = [line for line in done.stdout.splitlines() if line.startswith("SKIPPED")]
    assert all("docs/learn/" in line for line in skips), skips
