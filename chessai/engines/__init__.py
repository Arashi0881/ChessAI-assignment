"""Engines: the plug-in contract, baselines and the registry."""
from chessai.engines.base import (
    Candidate,
    Engine,
    SearchInfo,
    SearchLimit,
    SearchOutcome,
    SearchResult,
    allowed_time,
    engine_rng,
    run_search,
)
from chessai.engines.alphabeta import AlphaBetaEngine, MinimaxEngine
from chessai.engines.baselines import GreedyEngine, RandomEngine
from chessai.engines.mcts import MCTSEngine

ENGINES: dict[str, type[Engine]] = {
    RandomEngine.name: RandomEngine,
    GreedyEngine.name: GreedyEngine,
    MinimaxEngine.name: MinimaxEngine,      # the team's engines (stubs until written)
    AlphaBetaEngine.name: AlphaBetaEngine,
    MCTSEngine.name: MCTSEngine,
}

__all__ = [
    "ENGINES", "Candidate", "Engine", "SearchInfo", "SearchLimit", "SearchOutcome",
    "SearchResult", "allowed_time", "engine_rng", "run_search", "GreedyEngine", "RandomEngine", "MinimaxEngine", "AlphaBetaEngine", "MCTSEngine",
]
