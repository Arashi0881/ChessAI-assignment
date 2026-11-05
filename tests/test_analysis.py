import chess

from chessai.engines.base import Candidate, SearchInfo
from chessai.gui.analysis import analysis_lines, candidate_arrows, format_score

M = chess.Move.from_uci


def test_format_score():
    assert format_score(120, True) == "+1.20"
    assert format_score(120, False) == "-1.20"
    assert format_score(0, False) == "+0.00"
    assert format_score(None, True) == "?"


def test_alphabeta_style_lines():
    info = SearchInfo(nodes=12345, depth=5, score_cp=35, pv=[M("e2e4"), M("e7e5"), M("g1f3")])
    assert analysis_lines(chess.Board(), info, 2.0) == [
        "depth 5  nodes 12,345  6.2k nodes/s  score +0.35",
        "PV: e4 e5 Nf3",
    ]


def test_pv_stops_at_illegal_move():
    info = SearchInfo(nodes=10, pv=[M("e2e4"), M("e2e4")])
    assert analysis_lines(chess.Board(), info, 1.0)[1] == "PV: e4"


def test_mcts_style_lines():
    info = SearchInfo(nodes=2000, candidates=[
        Candidate(M("g1f3"), visits=812, value=0.54), Candidate(M("e2e4"), visits=600, value=0.5)])
    lines = analysis_lines(chess.Board(), info, 0.0)
    assert lines[0] == "nodes 2,000  — nodes/s"
    assert "Nf3  visits 812 (41%)  win 54%" in lines
    assert "e4  visits 600 (30%)  win 50%" in lines


def test_score_candidates():
    info = SearchInfo(nodes=20, candidates=[Candidate(M("e2e4"), score_cp=30)])
    assert "e4  score +0.30" in analysis_lines(chess.Board(), info, 1.0)


def test_large_rates():
    assert "2.5M nodes/s" in analysis_lines(chess.Board(), SearchInfo(nodes=5_000_000), 2.0)[0]


def test_candidate_arrows():
    four = SearchInfo(candidates=[Candidate(M(u)) for u in ("e2e4", "d2d4", "g1f3", "c2c4")])
    assert [w for _, w in candidate_arrows(four)] == [8, 5, 3]
    assert candidate_arrows(SearchInfo(pv=[M("e2e4"), M("e7e5")])) == [(M("e2e4"), 8)]
    assert candidate_arrows(SearchInfo()) == []
