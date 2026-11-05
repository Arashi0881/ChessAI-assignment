"""python -m chessai — play or watch chess in the GUI."""
from __future__ import annotations

import argparse

from chessai.engines import ENGINES
from chessai.session import GameSession


def build_parser() -> argparse.ArgumentParser:
    sides = ["human", *ENGINES]
    parser = argparse.ArgumentParser(prog="python -m chessai", description="Play or watch chess.")
    parser.add_argument("--white", default="human", choices=sides, help="who plays White")
    parser.add_argument("--black", default="greedy", choices=sides, help="who plays Black")
    parser.add_argument("--time", type=float, default=1.0, help="engine seconds per move")
    parser.add_argument("--fen", help="start from this position (FEN)")
    parser.add_argument("--seed", type=int, default=0, help="seed for the engines' randomness")
    parser.add_argument("--letters", action="store_true", help="draw pieces as letters")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.time <= 0:
        parser.error("--time must be positive")
    fen = args.fen or GameSession().start_fen
    try:
        GameSession(fen)
    except ValueError as exc:
        parser.error(str(exc))

    from chessai.gui.app import AppOptions, run  # import tkinter only when launching

    run(AppOptions(args.white, args.black, args.time, fen, args.seed, args.letters))


if __name__ == "__main__":
    main()
