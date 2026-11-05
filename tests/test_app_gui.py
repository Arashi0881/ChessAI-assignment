"""End-to-end checks of the Tk app. Skipped when no display is available."""
import threading
import time

import chess
import pytest

tk = pytest.importorskip("tkinter")

from chessai.engines import ENGINES  # noqa: E402
from chessai.engines.base import SearchResult  # noqa: E402
from chessai.gui.app import App, AppOptions  # noqa: E402

PROMO = "8/P6k/8/8/8/8/8/K7 w - - 0 1"
MATE = "7k/6Q1/6K1/8/8/8/8/8 b - - 0 1"
RELEASE = threading.Event()


class SlowEngine:
    name = "slow-test"
    def __init__(self, rng):
        pass
    def search(self, board, limit, stop):
        RELEASE.wait(5)
        return SearchResult(next(iter(board.legal_moves)))


class BadEngine:
    name = "bad-test"
    def __init__(self, rng):
        pass
    def search(self, board, limit, stop):
        return SearchResult(chess.Move.from_uci("e2e5"))


class BadInit:
    name = "badinit-test"
    def __init__(self, rng):
        raise RuntimeError("cannot start")


class Reentrant:
    """Notices stop only after 0.6 s; records if one object searches twice at once."""
    name = "reentrant-test"
    overlaps = 0
    def __init__(self, rng):
        self.active = 0
    def search(self, board, limit, stop):
        self.active += 1
        if self.active > 1:
            Reentrant.overlaps += 1
        while not stop.is_set():
            time.sleep(0.6)
        self.active -= 1
        return SearchResult(next(iter(board.legal_moves)))


class StringPv:
    name = "stringpv-test"
    def __init__(self, rng):
        pass
    def search(self, board, limit, stop):
        from chessai.engines import SearchInfo
        return SearchResult(chess.Move.from_uci("e2e4"), SearchInfo(nodes=1, pv=["e2e4"]))


class FakeEvent:
    def __init__(self, widget):
        self.widget = widget


@pytest.fixture
def make_app(monkeypatch):
    monkeypatch.setitem(ENGINES, "slow-test", SlowEngine)
    monkeypatch.setitem(ENGINES, "bad-test", BadEngine)
    monkeypatch.setitem(ENGINES, "badinit-test", BadInit)
    monkeypatch.setitem(ENGINES, "reentrant-test", Reentrant)
    monkeypatch.setitem(ENGINES, "stringpv-test", StringPv)
    Reentrant.overlaps = 0
    RELEASE.clear()
    roots = []

    def make(**kw):
        try:
            root = tk.Tk()
        except tk.TclError:
            pytest.skip("no display")
        root.withdraw()
        roots.append(root)
        return App(root, AppOptions(**kw))

    yield make
    RELEASE.set()
    for root in roots:
        root.destroy()


def pump(app, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.root.update()
        time.sleep(0.01)


def pump_until(app, condition, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end and not condition():
        app.root.update()
        time.sleep(0.01)
    return condition()


def test_human_vs_human_click_move(make_app):
    app = make_app(white="human", black="human")
    app.click_square(chess.E2)
    app.click_square(chess.E4)
    assert app.session.san_moves() == ["e4"]


def test_engine_replies(make_app):
    app = make_app(white="human", black="greedy", time_s=0.2)
    app.click_square(chess.E2)
    app.click_square(chess.E4)
    assert pump_until(app, lambda: len(app.session.san_moves()) == 2)


def test_undo_cancels_and_pauses(make_app):                 # Review Focus 4
    app = make_app(white="human", black="slow-test", time_s=5)
    app.click_square(chess.E2)
    app.click_square(chess.E4)
    assert pump_until(app, lambda: app.runner.busy)
    app.undo()
    assert not app.runner.busy and app.paused
    RELEASE.set()
    pump(app, 0.3)
    assert app.session.san_moves() == []


def test_illegal_engine_move_pauses(make_app):              # Review Focus 2
    app = make_app(white="bad-test", black="human", time_s=0.5)
    assert pump_until(app, lambda: "illegal move" in app.status_text())
    assert app.paused and app.session.san_moves() == []


def test_game_over_fen_starts_nothing(make_app):            # Review Focus 3
    app = make_app(white="greedy", black="greedy", fen=MATE)
    pump(app, 0.5)
    assert "1-0" in app.status_text() and "checkmate" in app.status_text()
    assert not app.runner.busy


def test_promotion_picker(make_app):                        # Review Focus 1
    app = make_app(white="human", black="human", fen=PROMO)
    app.click_square(chess.A7)
    app.click_square(chess.A8)
    assert app.pending_promotion is not None
    app.choose_promotion(None)
    assert app.session.san_moves() == [] and app.pending_promotion is None
    app.click_square(chess.A7)
    app.click_square(chess.A8)
    app.choose_promotion(chess.QUEEN)
    assert app.session.san_moves() == ["a8=Q"]


def test_empty_redo_keeps_engine_thinking(make_app):         # final review #1
    app = make_app(white="slow-test", black="human", time_s=5)
    assert pump_until(app, lambda: app.runner.busy)
    app.redo()
    assert app.runner.busy


def test_undo_with_nothing_to_undo_does_not_stall(make_app):  # final review #1
    app = make_app(white="greedy", black="human", time_s=0.2)
    app.undo()                                    # within the 300 ms start delay
    assert pump_until(app, lambda: len(app.session.san_moves()) == 1)


def test_engine_resumes_after_hint(make_app):                  # final review #2
    app = make_app(white="greedy", black="human", time_s=0.2)
    app.toggle_pause()
    app.hint_var.set("slow-test")
    app.hint()
    assert app.runner.busy
    app.toggle_pause()                            # resume while the hint runs
    RELEASE.set()
    assert pump_until(app, lambda: len(app.session.san_moves()) == 1)


def test_no_concurrent_search_on_one_engine(make_app):          # final review #3
    app = make_app(white="reentrant-test", black="human", time_s=10)
    assert pump_until(app, lambda: app.runner.busy)
    app.toggle_pause()
    app.toggle_pause()
    assert pump_until(app, lambda: app.runner.busy)
    pump(app, 0.3)
    assert Reentrant.overlaps == 0


def test_changing_other_side_keeps_search(make_app):            # final review #3
    app = make_app(white="slow-test", black="human", time_s=5)
    assert pump_until(app, lambda: app.runner.busy)
    app.black_var.set("greedy")
    app._side_changed(chess.BLACK)
    assert app.runner.busy


def test_engine_constructor_failure(make_app):                  # final review #4
    app = make_app(white="human", black="human")
    app.black_var.set("badinit-test")
    app._side_changed(chess.BLACK)
    assert "failed to start" in app.status_text() and app.paused
    assert app._engines[chess.BLACK] is None


def test_shortcuts_ignored_while_typing(make_app):              # final review #5
    app = make_app(white="human", black="human")
    app._shortcut(FakeEvent(app.time_spin), "flip")
    assert not app.flipped
    app._shortcut(FakeEvent(app.canvas), "flip")
    assert app.flipped


def test_too_many_unresponsive_engines_refused(make_app):       # final review #6
    app = make_app(white="human", black="human")
    app.hint_var.set("slow-test")
    for _ in range(2):
        app.hint()
        assert app.runner.busy
        app.new_game()
    app.hint()
    assert not app.runner.busy and "not responding" in app.status_text()


def test_new_game_closes_promotion_picker(make_app):            # final review #7
    app = make_app(white="human", black="human", fen=PROMO)
    app.click_square(chess.A7)
    app.click_square(chess.A8)
    assert app.pending_promotion is not None
    app.new_game()
    assert app.pending_promotion is None and app._promo_window is None
    app.click_square(chess.E2)
    app.click_square(chess.E4)
    assert app.session.san_moves() == ["e4"]


def test_bad_engine_report_is_shown_not_fatal(make_app):        # final review #4
    app = make_app(white="stringpv-test", black="human", time_s=0.5)
    assert pump_until(app, lambda: app.session.san_moves() == ["e4"])
    assert "pv cut" in app.analysis_text.get("1.0", "end")
    app.click_square(chess.E7)
    app.click_square(chess.E5)
    assert app.session.san_moves() == ["e4", "e5"]       # board still works


def test_new_game_from_opening(make_app):
    app = make_app(white="human", black="human")
    app.opening_var.set("Ruy Lopez")
    app.new_game()
    assert app.session.san_moves() == ["e4", "e5", "Nf3", "Nc6", "Bb5", "a6"]
    app.undo()
    assert app.session.san_moves() == ["e4", "e5", "Nf3", "Nc6", "Bb5"]
    app.opening_var.set("Start position")
    app.new_game()
    assert app.session.san_moves() == []


def test_unwritten_engine_in_gui(make_app):                  # phase 3 Review Focus 4
    import random
    from chessai.engines import alphabeta
    from chessai.engines.base import SearchLimit
    try:
        alphabeta.AlphaBetaEngine(random.Random(0)).search(chess.Board(), SearchLimit(depth=1), threading.Event())
    except NotImplementedError:
        pass
    except Exception:
        pytest.skip("alphabeta is written")
    else:
        pytest.skip("alphabeta is written")
    app = make_app(white="alphabeta", black="human", time_s=0.5)
    assert pump_until(app, lambda: "NotImplementedError" in app.status_text())
    assert app.paused and app.session.san_moves() == []
