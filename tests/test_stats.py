import pytest

from chessai.stats import PairScore, elo_from_score, elo_interval, format_elo, score, wilson_interval


def test_score():
    assert score(PairScore(6, 2, 2, (2, 2, 1.5, 0.5, 1))) == pytest.approx(0.7)


def test_elo_from_score():
    assert elo_from_score(0.5) == 0
    assert elo_from_score(0.75) == pytest.approx(190.85, abs=0.01)
    assert elo_from_score(1.0) == 800
    assert elo_from_score(0.0) == -800


def test_format_elo():
    assert format_elo(elo_from_score(1.0)) == "> +800"
    assert format_elo(elo_from_score(0.0)) == "< -800"
    assert format_elo(-35.4) == "-35"
    assert format_elo(35.4) == "+35"


def test_interval_perfect_score():
    assert elo_interval(PairScore(10, 0, 0, (2,) * 5)) == (800, 800)


def test_interval_symmetric():
    low, high = elo_interval(PairScore(4, 0, 4, (2, 0, 2, 0)))
    assert low < 0 < high
    assert low == pytest.approx(-high, abs=1e-9)


def test_interval_one_pair_is_unknown():
    assert elo_interval(PairScore(1, 1, 0, (1.5,))) == (-800, 800)


def test_wilson():
    low, high = wilson_interval(5, 10)
    assert low == pytest.approx(0.2366, abs=1e-4)
    assert high == pytest.approx(0.7634, abs=1e-4)
    assert wilson_interval(0, 0) == (0.0, 1.0)
