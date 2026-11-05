"""tkinter chess GUI. Thin: rules in python-chess, game record in GameSession,
searches on EngineRunner's thread, drawing decisions in geometry/analysis."""
from __future__ import annotations

import sys
import tkinter as tk
import tkinter.font as tkfont
from dataclasses import dataclass
from tkinter import messagebox, simpledialog, ttk

import chess

from chessai.data import load_openings
from chessai.engines import ENGINES, SearchInfo, SearchLimit, allowed_time, engine_rng
from chessai.gui.analysis import analysis_lines, candidate_arrows
from chessai.gui.engine_runner import EngineRunner, RunnerResult
from chessai.gui.geometry import (
    find_move, needs_promotion, pick_piece_font, piece_text, square_at, square_center,
    square_origin, targets,
)
from chessai.session import GameSession

HUMAN = "human"
START_POSITION = "Start position"
LIGHT, DARK = "#f0d9b5", "#b58863"
LAST_LIGHT, LAST_DARK = "#e8e18e", "#c9b45a"
SELECTED = "#8fc78f"
CHECK = "#e06666"
TARGET = "#2f6f3e"
ARROW = "#2f6fde"
POLL_MS = 50
MOVE_DELAY_MS = 300           # pause before an engine moves, so engine games are watchable
MIN_TIME_S, MAX_TIME_S = 0.1, 60.0
MAX_ZOMBIES = 2            # cancelled searches still running before new ones are refused
SHORTCUTS = {
    "<F2>": "new_game", "<Control-z>": "undo", "<Control-y>": "redo",
    "<KeyPress-f>": "flip", "<KeyPress-h>": "hint", "<space>": "toggle_pause",
    "<KeyPress-a>": "toggle_analysis", "<Escape>": "deselect",
}


@dataclass(frozen=True)
class AppOptions:
    white: str = HUMAN
    black: str = "greedy"
    time_s: float = 1.0
    fen: str = chess.STARTING_FEN
    seed: int = 0
    letters: bool = False


def board_square_size(screen_w: int, screen_h: int, scale: float) -> int:
    """Square size in pixels: fits half the screen width / 70% height, 40–90 px at 96 dpi."""
    fit = min(int(screen_w * 0.5) // 8, int(screen_h * 0.7) // 8)
    return max(round(40 * scale), min(round(90 * scale), fit))


class App:
    def __init__(self, root: tk.Tk, options: AppOptions) -> None:
        self.root = root
        self.options = options
        self.session = GameSession(options.fen)
        self.runner = EngineRunner()
        self.paused = False
        self.flipped = False
        self.selected: chess.Square | None = None
        self.pending_promotion: tuple[chess.Square, chess.Square] | None = None
        self._promo_window: tk.Toplevel | None = None
        self._engines: dict[chess.Color, object | None] = {chess.WHITE: None, chess.BLACK: None}
        self._engine_errors: dict[chess.Color, str] = {}
        self._search_color: chess.Color = chess.WHITE
        self._purpose: str | None = None           # "move" or "hint" while searching
        self._search_fen: str | None = None
        self._search_label = ""
        self._analysis: tuple[str, SearchInfo, float, str] | None = None  # label, info, elapsed, fen
        self._message = ""
        self._poll_job: str | None = None
        self._start_job: str | None = None
        try:
            self.openings = {o.name: o for o in load_openings()}
        except (OSError, ValueError):   # a broken data file must not stop the GUI
            self.openings = {}

        root.title("Chess AI")
        root.resizable(False, False)
        scale = root.winfo_fpixels("1i") / 96
        self.size = board_square_size(root.winfo_screenwidth(), root.winfo_screenheight(), scale)
        self.piece_font = pick_piece_font(tkfont.families(root))
        self._build(options)
        if self.piece_font is None:  # no font with chess symbols: letters only
            self.letters.set(True)
        bindings = dict(SHORTCUTS)
        for key, method in SHORTCUTS.items():
            if key.startswith("<KeyPress-") and len(key) == 12:
                bindings[key.upper().replace("KEYPRESS", "KeyPress")] = method
        if root.tk.call("tk", "windowingsystem") == "aqua":  # macOS users expect ⌘Z / ⌘Y
            bindings.update({"<Command-z>": "undo", "<Command-y>": "redo"})
        for key, method in bindings.items():
            root.bind(key, lambda e, m=method: self._shortcut(e, m))
        self._make_engines()
        self._position_changed()

    # --- construction -------------------------------------------------------------

    def _build(self, options: AppOptions) -> None:
        board_px = self.size * 8
        self.canvas = tk.Canvas(self.root, width=board_px, height=board_px, highlightthickness=0)
        self.canvas.grid(row=0, column=0, padx=8, pady=8, sticky="n")
        self.canvas.bind("<Button-1>", self._on_click)

        panel = tk.Frame(self.root)
        panel.grid(row=0, column=1, padx=(0, 8), pady=8, sticky="ns")
        choices = [HUMAN, *ENGINES]
        self.white_var = tk.StringVar(value=options.white)
        self.black_var = tk.StringVar(value=options.black)
        self.hint_var = tk.StringVar(value="greedy" if "greedy" in ENGINES else next(iter(ENGINES)))
        self.time_var = tk.StringVar(value=f"{options.time_s:g}")
        self.show_analysis = tk.BooleanVar(value=True)
        self.letters = tk.BooleanVar(value=options.letters)

        row = 0
        for label, var, color in (("White", self.white_var, chess.WHITE), ("Black", self.black_var, chess.BLACK)):
            tk.Label(panel, text=label).grid(row=row, column=0, sticky="w")
            tk.OptionMenu(panel, var, *choices, command=lambda _v, c=color: self._side_changed(c)).grid(
                row=row, column=1, sticky="we")
            row += 1
        tk.Label(panel, text="Hint engine").grid(row=row, column=0, sticky="w")
        tk.OptionMenu(panel, self.hint_var, *ENGINES).grid(row=row, column=1, sticky="we")
        row += 1
        tk.Label(panel, text="Opening").grid(row=row, column=0, sticky="w")
        self.opening_var = tk.StringVar(value=START_POSITION)
        # a Combobox scrolls; a 51-entry OptionMenu can run off a laptop screen
        ttk.Combobox(panel, textvariable=self.opening_var, values=[START_POSITION, *self.openings],
                     state="readonly", width=22, height=15).grid(row=row, column=1, sticky="we")
        row += 1
        tk.Label(panel, text="Seconds / move").grid(row=row, column=0, sticky="w")
        self.time_spin = tk.Spinbox(panel, from_=MIN_TIME_S, to=MAX_TIME_S, increment=0.1, width=6,
                                    textvariable=self.time_var)
        self.time_spin.grid(row=row, column=1, sticky="w")
        row += 1

        buttons = tk.Frame(panel)
        buttons.grid(row=row, column=0, columnspan=2, pady=6, sticky="we")
        row += 1
        specs = [
            ("New game (F2)", self.new_game), ("From FEN…", self.from_fen), ("Flip (F)", self.flip),
            ("Undo", self.undo), ("Redo", self.redo), ("Hint (H)", self.hint),
            ("Stop", self.stop_search), ("Pause", self.toggle_pause), ("Copy PGN", self.copy_pgn),
            ("Copy FEN", self.copy_fen),
        ]
        for i, (text, command) in enumerate(specs):
            button = tk.Button(buttons, text=text, command=command, width=12)
            button.grid(row=i // 2, column=i % 2, padx=2, pady=2, sticky="we")
            if text == "Pause":
                self.pause_btn = button
        tk.Checkbutton(panel, text="Show analysis (A)", variable=self.show_analysis,
                       command=self._draw).grid(row=row, column=0, columnspan=2, sticky="w")
        row += 1
        tk.Checkbutton(panel, text="Letter pieces", variable=self.letters,
                       command=self._draw).grid(row=row, column=0, columnspan=2, sticky="w")
        row += 1
        tk.Label(panel, text="Moves").grid(row=row, column=0, sticky="w")
        row += 1
        self.moves_text = tk.Text(panel, width=30, height=10, state="disabled", wrap="word")
        self.moves_text.grid(row=row, column=0, columnspan=2, sticky="we")
        row += 1
        tk.Label(panel, text="Analysis").grid(row=row, column=0, sticky="w")
        row += 1
        self.analysis_text = tk.Text(panel, width=30, height=8, state="disabled", wrap="word")
        self.analysis_text.grid(row=row, column=0, columnspan=2, sticky="we")

        self.status_var = tk.StringVar()
        tk.Entry(self.root, textvariable=self.status_var, state="readonly", relief="flat").grid(
            row=1, column=0, columnspan=2, sticky="we", padx=8, pady=(0, 8))

    # --- public actions (buttons, shortcuts, tests) ---------------------------------

    def status_text(self) -> str:
        return self.status_var.get()

    def click_square(self, square: chess.Square) -> None:
        board = self.session.board
        if self.pending_promotion or self.session.outcome() or not self._human_to_move():
            return
        if self._purpose == "move":
            return
        piece = board.piece_at(square)
        if self.selected is not None and square in targets(board, self.selected):
            if needs_promotion(board, self.selected, square):
                self.pending_promotion = (self.selected, square)
                self._open_promotion_picker()
            else:
                self._human_move(find_move(board, self.selected, square))
            return
        if piece is not None and piece.color == board.turn and square != self.selected:
            self.selected = square
        else:
            self.selected = None
        self._draw()

    def choose_promotion(self, piece_type: chess.PieceType | None) -> None:
        if self._promo_window is not None:
            self._promo_window.destroy()
            self._promo_window = None
        pending, self.pending_promotion = self.pending_promotion, None
        if pending is None:
            return
        move = find_move(self.session.board, *pending, piece_type) if piece_type else None
        if move is None:
            self.selected = None
            self._draw()
        else:
            self._human_move(move)

    def new_game(self) -> None:
        self._abandon_search()
        self.session = GameSession()
        opening = self.openings.get(self.opening_var.get())
        for move in opening.moves if opening else ():
            self.session.play(move)
        self.paused = False
        self._make_engines()
        self._analysis = None
        self._position_changed()

    def from_fen(self) -> None:
        fen = simpledialog.askstring("Position from FEN", "FEN:", parent=self.root)
        if not fen:
            return
        try:
            session = GameSession(fen.strip())
        except ValueError as exc:
            messagebox.showerror("Invalid position", str(exc), parent=self.root)
            return
        self._abandon_search()
        self.session = session
        self.paused = True
        self._make_engines()
        self._analysis = None
        self._position_changed()

    def flip(self) -> None:
        self.flipped = not self.flipped
        self._draw()

    def undo(self) -> None:
        if not self.session.can_undo:
            return  # nothing to take back: leave any engine search alone
        self._abandon_search()
        self.session.undo()
        self.paused = True
        self._position_changed()

    def redo(self) -> None:
        if not self.session.can_redo:
            return
        self._abandon_search()
        self.session.redo()
        self.paused = True
        self._position_changed()

    def hint(self) -> None:
        if self.session.outcome() or self.runner.busy or self._start_job is not None:
            return
        name = self.hint_var.get()
        engine = ENGINES[name](engine_rng(self.options.seed, f"{name}:hint"))
        self._start_search(engine, "hint", f"Hint ({name})")

    def stop_search(self) -> None:
        self.runner.stop()

    def toggle_pause(self) -> None:
        self.paused = not self.paused
        if self.paused:
            if self._purpose == "move" or self._start_job is not None:
                self._abandon_search()  # also drops an engine start that is still pending
        else:
            self._message = ""
        self._update_status()
        self._maybe_start_engine()

    def toggle_analysis(self) -> None:
        self.show_analysis.set(not self.show_analysis.get())
        self._draw()

    def deselect(self) -> None:
        self.selected = None
        self._draw()

    def _shortcut(self, event: tk.Event, method: str) -> None:
        """Run a keyboard shortcut, unless the user is typing into a text field."""
        if isinstance(event.widget, (tk.Entry, tk.Spinbox, tk.Text)):
            return
        getattr(self, method)()

    def copy_pgn(self) -> None:
        self._copy(self.session.pgn(self.white_var.get(), self.black_var.get()), "PGN copied")

    def copy_fen(self) -> None:
        self._copy(self.session.fen, "FEN copied")

    # --- engines --------------------------------------------------------------------

    def _side_name(self, color: chess.Color) -> str:
        return (self.white_var if color == chess.WHITE else self.black_var).get()

    def _human_to_move(self) -> bool:
        return self._side_name(self.session.board.turn) == HUMAN

    def _make_engine(self, color: chess.Color):
        name = self._side_name(color)
        self._engine_errors.pop(color, None)
        if name == HUMAN:
            return None
        side = "white" if color == chess.WHITE else "black"
        try:
            return ENGINES[name](engine_rng(self.options.seed, f"{name}:{side}"))
        except Exception as exc:  # a broken engine constructor must not break the GUI
            self._engine_errors[color] = f"{name} failed to start: {type(exc).__name__}: {exc}"
            self.paused = True
            return None

    def _make_engines(self) -> None:
        for color in (chess.WHITE, chess.BLACK):
            self._engines[color] = self._make_engine(color)

    def _side_changed(self, color: chess.Color) -> None:
        mover = color == self.session.board.turn
        if mover and (self._purpose == "move" or self._start_job is not None):
            self._abandon_search()
        self._engines[color] = self._make_engine(color)
        self._update_status()
        self._maybe_start_engine()

    def _time_s(self) -> float:
        try:
            value = float(self.time_var.get())
        except ValueError:
            return 1.0
        return min(MAX_TIME_S, max(MIN_TIME_S, value))

    def _maybe_start_engine(self) -> None:
        if (
            self.paused or self.session.outcome() or self.runner.busy
            or self._start_job is not None or self._human_to_move()
        ):
            return
        self._start_job = self.root.after(MOVE_DELAY_MS, self._start_engine_move)

    def _start_engine_move(self) -> None:
        self._start_job = None
        if self.paused or self.session.outcome() or self.runner.busy or self._human_to_move():
            return
        color = self.session.board.turn
        if self._engines[color] is None:  # its constructor failed
            self.paused = True
            self._update_status()
            return
        side = "White" if color == chess.WHITE else "Black"
        self._search_color = color
        self._start_search(self._engines[color], "move", f"{side} ({self._side_name(color)})")

    def _start_search(self, engine, purpose: str, label: str) -> None:
        zombies = self.runner.zombies
        if zombies >= MAX_ZOMBIES:
            self._message = (
                f"engine not responding: {zombies} stopped searches are still running "
                "— restart the program to free the CPU"
            )
            self.paused = True
            self._update_status()
            return
        self._purpose = purpose
        self._search_fen = self.session.fen
        self._search_label = label
        self.runner.start(engine, self.session.board, SearchLimit(time_s=self._time_s()))
        self._poll()

    def _abandon_search(self) -> None:
        if self._start_job is not None:
            self.root.after_cancel(self._start_job)
            self._start_job = None
        if self._poll_job is not None:
            self.root.after_cancel(self._poll_job)
            self._poll_job = None
        self._close_promotion()
        if self.runner.busy:
            self.runner.cancel()
            if self._purpose == "move":
                # The cancelled thread may still be using this engine object:
                # give the side a fresh one so two searches never share state.
                self._engines[self._search_color] = self._make_engine(self._search_color)
        self._purpose = None

    def _poll(self) -> None:
        self._poll_job = None
        result = self.runner.poll()
        if result is None:
            if self.runner.busy:
                self._update_status()
                self._poll_job = self.root.after(POLL_MS, self._poll)
            return
        self._finish_search(result)

    def _finish_search(self, result: RunnerResult) -> None:
        purpose, self._purpose = self._purpose, None
        outcome = result.outcome
        if self._search_fen != self.session.fen:
            self._maybe_start_engine()
            return  # position changed meanwhile; the answer is stale
        if outcome.result is not None:
            label = self._search_label
            if outcome.notes:  # the engine reported something malformed; say what was dropped
                label += "\n(" + "; ".join(outcome.notes) + ")"
            self._analysis = (label, outcome.result.info, outcome.elapsed, self._search_fen)
        if not outcome.playable:
            self._message = f"{self._search_label}: {outcome.problem}"
            if purpose == "move":
                self.paused = True
                self._message += " — paused"
            self._draw()
            self._maybe_start_engine()
            return
        move = outcome.result.move
        san = self.session.board.san(move)
        if purpose == "hint":
            self._message = f"{self._search_label} suggests {san} ({outcome.elapsed:.1f} s)"
            self._draw()
            self._maybe_start_engine()  # an engine may have been waiting for the hint
            return
        self.session.play(move)
        self._position_changed()
        if outcome.problem:  # overtime: played, but say so
            self._message = f"{self._search_label} played {san} — {outcome.problem}"
            self._update_status()

    # --- human moves ------------------------------------------------------------------

    def _human_move(self, move: chess.Move | None) -> None:
        if move is None:
            return
        if self._purpose == "hint":
            self._abandon_search()
        self.session.play(move)
        self.paused = False
        self._position_changed()

    def _open_promotion_picker(self) -> None:
        window = tk.Toplevel(self.root)
        window.title("Promote to")
        window.transient(self.root)
        window.resizable(False, False)
        color = self.session.board.turn
        for piece_type in (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT):
            text = piece_text(chess.Piece(piece_type, color), self.letters.get())
            family = self.piece_font if self.piece_font and not self.letters.get() else "TkDefaultFont"
            tk.Button(window, text=text, width=3, font=(family, 20),
                      command=lambda p=piece_type: self.choose_promotion(p)).pack(side="left", padx=4, pady=4)
        window.protocol("WM_DELETE_WINDOW", lambda: self.choose_promotion(None))
        window.bind("<Escape>", lambda _e: self.choose_promotion(None))
        self._promo_window = window

    def _close_promotion(self) -> None:
        if self._promo_window is not None:
            self._promo_window.destroy()
            self._promo_window = None
        self.pending_promotion = None

    def _on_click(self, event: tk.Event) -> None:
        square = square_at(event.x, event.y, self.size, self.flipped)
        if square is not None:
            self.click_square(square)

    # --- drawing ------------------------------------------------------------------------

    def _position_changed(self) -> None:
        self._close_promotion()
        self.selected = None
        self._message = ""
        self._update_moves()
        self._draw()
        self._maybe_start_engine()

    def _draw(self) -> None:
        board, size, canvas = self.session.board, self.size, self.canvas
        canvas.delete("all")
        last = self.session.last_move
        last_squares = {last.from_square, last.to_square} if last else set()
        check_square = board.king(board.turn) if board.is_check() else None
        dots = targets(board, self.selected) if self.selected is not None else set()
        family = "TkDefaultFont" if self.letters.get() or not self.piece_font else self.piece_font
        font = (family, -int(size * 0.72))
        for square in chess.SQUARES:
            x, y = square_origin(square, size, self.flipped)
            light = (chess.square_file(square) + chess.square_rank(square)) % 2 == 1
            fill = LIGHT if light else DARK
            if square in last_squares:
                fill = LAST_LIGHT if light else LAST_DARK
            if square == self.selected:
                fill = SELECTED
            if square == check_square:
                fill = CHECK
            canvas.create_rectangle(x, y, x + size, y + size, fill=fill, width=0)
            piece = board.piece_at(square)
            if piece is not None:
                canvas.create_text(x + size / 2, y + size / 2, text=piece_text(piece, self.letters.get()),
                                   font=font, fill="#000000")
            if square in dots:
                r = size * 0.14
                cx, cy = x + size / 2, y + size / 2
                canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=TARGET, width=0)
        self._draw_coordinates()
        self._draw_analysis()
        self._update_status()

    def _draw_coordinates(self) -> None:
        small = ("TkDefaultFont", -max(9, self.size // 6))
        for i in range(8):
            file_sq = chess.square(i, 0 if not self.flipped else 7)
            x, y = square_origin(file_sq, self.size, self.flipped)
            self.canvas.create_text(x + self.size - 3, y + self.size - 2, text=chess.FILE_NAMES[i],
                                    anchor="se", font=small, fill="#555555")
            rank_sq = chess.square(0 if not self.flipped else 7, i)
            x, y = square_origin(rank_sq, self.size, self.flipped)
            self.canvas.create_text(x + 3, y + 2, text=chess.RANK_NAMES[i], anchor="nw",
                                    font=small, fill="#555555")

    def _draw_analysis(self) -> None:
        lines: list[str] = []
        if self._analysis is not None and self.show_analysis.get():
            label, info, elapsed, fen = self._analysis
            lines = [label, *analysis_lines(chess.Board(fen), info, elapsed)]
            if fen == self.session.fen:  # arrows only while that position is on the board
                for move, width in candidate_arrows(info):
                    x1, y1 = square_center(move.from_square, self.size, self.flipped)
                    x2, y2 = square_center(move.to_square, self.size, self.flipped)
                    self.canvas.create_line(
                        x1, y1, x2, y2, width=width, fill=ARROW, arrow="last",
                        arrowshape=(width * 2.5, width * 3, width * 1.2), tags="arrow",
                    )
        self._set_text(self.analysis_text, "\n".join(lines))

    def _update_moves(self) -> None:
        start = chess.Board(self.session.start_fen)
        number, white = start.fullmove_number, start.turn == chess.WHITE
        parts = [] if white else [f"{number}..."]
        for san in self.session.san_moves():
            if white:
                parts.append(f"{number}.")
            parts.append(san)
            if not white:
                number += 1
            white = not white
        self._set_text(self.moves_text, " ".join(parts))

    def _update_status(self) -> None:
        end = self.session.outcome()
        if end is not None:
            text = f"Game over: {end.result} ({end.reason})"
        elif self._engine_errors:
            text = next(iter(self._engine_errors.values()))
        elif self._message:
            text = self._message
        elif self.runner.busy:
            text = f"{self._search_label} thinking… {self.runner.elapsed:.1f} s"
            budget = allowed_time(SearchLimit(time_s=self._time_s()))
            if budget is not None and self.runner.elapsed > budget:
                text += " — not responding to its time limit (press Stop)"
        else:
            side = "White" if self.session.board.turn == chess.WHITE else "Black"
            text = f"{side} to move"
            if self.paused and not self._human_to_move():
                text += " — paused (Space to resume)"
        self.status_var.set(f"{text}    seed {self.options.seed}")
        if hasattr(self, "pause_btn"):
            self.pause_btn.config(text="Resume" if self.paused else "Pause")

    @staticmethod
    def _set_text(widget: tk.Text, text: str) -> None:
        widget.config(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.config(state="disabled")

    def _copy(self, text: str, message: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self._message = message
        self._update_status()


def _enable_windows_dpi_awareness() -> None:
    """Avoid a blurry, bitmap-scaled window on Windows high-DPI displays."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


def run(options: AppOptions) -> None:
    _enable_windows_dpi_awareness()
    root = tk.Tk()
    App(root, options)
    root.mainloop()
