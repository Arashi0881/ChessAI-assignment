"""Output folders and run manifests shared by the match, puzzle and benchmark tools."""
from __future__ import annotations

import csv
import datetime
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

import chess

ROOT = Path(__file__).resolve().parent.parent


def prepare_output_dir(path: Path, force: bool) -> Path:
    """Create `path`; refuse to reuse a folder that already holds results unless `force`."""
    path = Path(path)
    if path.exists() and any(path.iterdir()) and not force:
        raise FileExistsError(f"{path} already has results; pass --force to overwrite or choose another --out")
    path.mkdir(parents=True, exist_ok=True)
    return path


def _git_commit() -> str | None:
    try:
        done = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    return done.stdout.strip() or None


def write_manifest(path: Path, args: dict, extra: dict) -> None:
    """Write manifest.json: everything needed to reproduce or explain a run."""
    manifest = {
        "args": args,
        "seed": args.get("seed"),
        "git_commit": _git_commit(),
        "chess_version": chess.__version__,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        **extra,
    }
    (Path(path) / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str) + "\n", encoding="utf-8")


def update_manifest(path: Path, **fields) -> None:
    """Add or change fields in an existing manifest.json (e.g. complete=True at the end)."""
    file = Path(path) / "manifest.json"
    manifest = json.loads(file.read_text(encoding="utf-8"))
    manifest.update(fields)
    file.write_text(json.dumps(manifest, indent=2, default=str) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    with Path(path).open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, columns)
        writer.writeheader()
        writer.writerows(rows)


class CsvAppender:
    """A CSV written one row at a time and flushed, so a killed run keeps every finished row."""

    def __init__(self, path: Path, columns: list[str]) -> None:
        self._file = Path(path).open("w", newline="", encoding="utf-8")
        self._writer = csv.DictWriter(self._file, columns)
        self._writer.writeheader()
        self._file.flush()

    def append(self, row: dict) -> None:
        self._writer.writerow(row)
        self._file.flush()

    def close(self) -> None:
        self._file.close()
