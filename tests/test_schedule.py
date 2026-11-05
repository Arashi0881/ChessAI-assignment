import csv
import json
import time

import pytest

from chessai.data import load_openings
from chessai.match.__main__ import main
from chessai.match.game import GameSpec
from chessai.match.schedule import build_schedule, run_schedule, summarize
from chessai.output import prepare_output_dir

OPENINGS = load_openings()[:3]


def test_schedule_shape():
    specs = build_schedule(["a", "b"], [0.1, 0.5], 4, OPENINGS, seed=7)
    assert len(specs) == 8
    assert [s.index for s in specs] == list(range(8))
    assert len({s.seed for s in specs}) == 8
    assert specs[0].seed == 7 * 1_000_003
    for t in (0.1, 0.5):
        group = [s for s in specs if s.time_s == t]
        assert [s.white for s in group] == ["a", "b", "a", "b"]
        for first, second in zip(group[::2], group[1::2]):
            assert first.opening == second.opening
            assert first.opening_moves == second.opening_moves
            assert (first.white, first.black) == (second.black, second.white)
        assert len({s.opening for s in group}) == 2


def test_schedule_reproducible():
    assert build_schedule(["a", "b"], [0.1], 6, OPENINGS, 3) == build_schedule(["a", "b"], [0.1], 6, OPENINGS, 3)


def test_three_engines_make_three_pairs():
    specs = build_schedule(["a", "b", "c"], [0.1], 2, OPENINGS, 0)
    assert {frozenset((s.white, s.black)) for s in specs} == {
        frozenset("ab"), frozenset("ac"), frozenset("bc")}


def test_odd_games_rejected():
    with pytest.raises(ValueError, match="even"):
        build_schedule(["a", "b"], [0.1], 7, OPENINGS, 0)


def test_too_many_games_for_openings():
    with pytest.raises(ValueError, match="openings"):
        build_schedule(["a", "b"], [0.1], 8, OPENINGS, 0)


def outcomes(records):
    return [(r.result, r.termination, r.plies) for r in records]


def test_jobs_do_not_change_results():
    specs = build_schedule(["random", "greedy"], [0.02], 4, OPENINGS, 1)
    seen = []
    one = run_schedule(specs, jobs=1, progress=seen.append)
    two = run_schedule(specs, jobs=2)
    assert outcomes(one) == outcomes(two)
    assert [r.index for r in two] == [0, 1, 2, 3]
    assert len(seen) == 4


def test_summarize():
    specs = build_schedule(["random", "greedy"], [0.02], 4, OPENINGS, 1)
    records = run_schedule(specs, jobs=1)
    pair = summarize(records, "greedy", "random", 0.02)
    assert pair.wins + pair.draws + pair.losses == 4
    assert len(pair.pair_points) == 2
    assert sum(pair.pair_points) == pair.wins + pair.draws / 2


def test_hang_in_worker_process():
    specs = [GameSpec(i, i, w, b, 0.05, "Start", ()) for i, (w, b) in
             enumerate([("hang-test", "random"), ("random", "hang-test")])]
    start = time.perf_counter()
    records = run_schedule(specs, jobs=2, engine_module="tests.fake_engines")
    assert time.perf_counter() - start < 15
    assert [r.termination for r in records] == ["forfeit: no answer (white)", "forfeit: no answer (black)"]


def test_output_dir_guard(tmp_path):
    out = tmp_path / "run"
    assert prepare_output_dir(out, force=False) == out
    (out / "games.csv").write_text("old")
    with pytest.raises(FileExistsError, match="--force"):
        prepare_output_dir(out, force=False)
    assert prepare_output_dir(out, force=True) == out


@pytest.mark.parametrize("extra", [["--engines", "random", "nobody"],
                                   ["--engines", "random", "greedy", "--time", "nan"],
                                   ["--engines", "random", "greedy", "--time", "0"],
                                   ["--engines", "random", "random"],
                                   ["--engines", "random", "greedy", "--games", "500"]])
def test_cli_rejects_bad_input(tmp_path, extra):
    with pytest.raises(SystemExit) as exc:
        main([*extra, "--out", str(tmp_path / "x")])
    assert exc.value.code == 2
    assert not (tmp_path / "x").exists()


def test_cli_run(tmp_path, capsys):
    out = tmp_path / "run"
    main(["--engines", "random", "greedy", "--time", "0.02", "--games", "2", "--jobs", "1", "--out", str(out)])
    with (out / "games.csv").open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert list(rows[0])[:11] == ["index", "seed", "white", "black", "time_s", "opening", "white_eval",
                                  "black_eval", "result", "termination", "plies"]
    assert {rows[0]["white_eval"], rows[0]["black_eval"]} == {"none", "material 1/3/3/5/9"}
    assert "white_nps" in rows[0] and "black_depth_mean" in rows[0]
    with (out / "summary.csv").open() as f:
        summary = list(csv.DictReader(f))
    assert list(summary[0]) == ["a", "b", "time_s", "games", "wins", "draws", "losses", "score",
                                "elo", "elo_low", "elo_high", "forfeits_a", "forfeits_b"]
    assert (out / "games.pgn").read_text().count("[Event ") == 2
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["args"]["engines"] == ["random", "greedy"]
    assert "chess_version" in manifest
    assert "random" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        main(["--engines", "random", "greedy", "--games", "2", "--out", str(out)])


@pytest.mark.parametrize("jobs", [1, 2])
def test_dead_worker_is_a_forfeit(jobs):                     # final review #2
    specs = [GameSpec(i, i, w, b, 0.05, "Start", ()) for i, (w, b) in
             enumerate([("exit-test", "random"), ("random", "exit-test"), ("random", "greedy")])]
    start = time.perf_counter()
    records = run_schedule(specs, jobs=jobs, engine_module="tests.fake_engines")
    assert time.perf_counter() - start < 30
    assert [r.termination for r in records[:2]] == ["forfeit: crash (white)", "forfeit: crash (black)"]
    assert [r.result for r in records[:2]] == ["0-1", "1-0"]
    assert records[2].plies > 0


def test_interrupted_match_keeps_finished_games(tmp_path, monkeypatch):   # final review #1
    import chessai.match.__main__ as cli
    real = cli.run_schedule

    def interrupted(specs, jobs, progress=None, engine_module=None):
        real(specs[:2], 1, progress)
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "run_schedule", interrupted)
    out = tmp_path / "run"
    with pytest.raises(SystemExit) as exc:
        main(["--engines", "random", "greedy", "--time", "0.02", "--games", "4", "--jobs", "1", "--out", str(out)])
    assert exc.value.code == 130
    with (out / "games.csv").open() as f:
        assert len(list(csv.DictReader(f))) == 2
    with (out / "summary.csv").open() as f:
        assert next(csv.DictReader(f))["games"] == "2"
    assert (out / "games.pgn").read_text().count("[Event ") == 2
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["complete"] is False
    assert manifest["games_done"] == 2


def test_completed_match_manifest(tmp_path):
    out = tmp_path / "run"
    main(["--engines", "random", "greedy", "--time", "0.02", "--games", "2", "--jobs", "2", "--out", str(out)])
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["complete"] is True
    with (out / "games.csv").open() as f:
        assert [r["index"] for r in csv.DictReader(f)] == ["0", "1"]


def test_default_jobs_leave_a_core_per_game():               # final review minor 3
    import os
    from chessai.match.__main__ import build_parser
    jobs = build_parser().parse_args(["--engines", "a", "b", "--out", "x"]).jobs
    assert 1 <= jobs <= max(1, (os.cpu_count() or 2) // 2)
