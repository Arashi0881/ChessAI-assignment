"""Step 7: the two engines play each other. Read docs/learn/07-fair-comparison.md first."""
import chess

import chessai.match.game as game
from chessai.data import load_openings
from chessai.engines import ENGINES
from chessai.engines.base import SearchLimit, engine_rng
from tests.learn._steps import run_engine, step

TUTORIAL = "docs/learn/07-fair-comparison.md"


def written(name):
    run_engine(ENGINES[name](engine_rng(0, name)), chess.Board(), SearchLimit(time_s=0.1, depth=1, iterations=10))


@step(TUTORIAL)
def test_alphabeta_and_mcts_play_a_clean_game(monkeypatch):
    written("alphabeta")
    written("mcts")
    monkeypatch.setattr(game, "MAX_PLIES", 20)      # a short game is enough to show both work
    italian = next(o for o in load_openings() if o.name == "Italian Game")
    moves = tuple(m.uci() for m in italian.moves)
    for white, black in (("alphabeta", "mcts"), ("mcts", "alphabeta")):
        record = game.play_game(game.GameSpec(0, 1, white, black, 0.1, italian.name, moves))
        assert not record.termination.startswith("forfeit"), f"{white} vs {black}: {record.termination}"


def test_same_evaluation_for_both():
    """The comparison holds the evaluation fixed, so differences come from the search."""
    assert ENGINES["alphabeta"].evaluation == ENGINES["mcts"].evaluation
