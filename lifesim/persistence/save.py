"""Saving and loading the complete simulation state.

A save file is a gzip-compressed pickle of the whole Simulation, including the random
number generator, so a loaded simulation continues exactly as the original would have.
Only load save files you created yourself: unpickling can run arbitrary code.
"""

from __future__ import annotations

import gzip
import pickle
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from lifesim.core.simulation import Simulation

FORMAT = "lifesim-save"
VERSION = 1
SUFFIX = ".lifesim"
SAVE_DIR = Path("saves")
QUICKSAVE = SAVE_DIR / f"schnellspeicher{SUFFIX}"
# Minions reference each other (targets, perceptions), which makes the object graph deep.
RECURSION_LIMIT = 50_000


class SaveError(Exception):
    pass


@contextmanager
def _deep_recursion():
    old = sys.getrecursionlimit()
    sys.setrecursionlimit(max(old, RECURSION_LIMIT))
    try:
        yield
    finally:
        sys.setrecursionlimit(old)


def save(sim: Simulation, path: Path | str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"format": FORMAT, "version": VERSION, "saved": datetime.now().isoformat(), "sim": sim}
    tmp = path.with_suffix(path.suffix + ".tmp")
    with _deep_recursion(), gzip.open(tmp, "wb") as f:
        pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
    tmp.replace(path)  # never leave a half-written save behind
    return path


def load(path: Path | str) -> Simulation:
    path = Path(path)
    try:
        with _deep_recursion(), gzip.open(path, "rb") as f:
            payload = pickle.load(f)
    except (OSError, EOFError, pickle.UnpicklingError, AttributeError, ImportError) as e:
        raise SaveError(f"{path.name} ist kein lesbarer Spielstand ({e})") from e
    if not isinstance(payload, dict) or payload.get("format") != FORMAT:
        raise SaveError(f"{path.name} ist kein Life-Simulator-Spielstand")
    if payload.get("version") != VERSION:
        raise SaveError(f"{path.name} hat eine nicht unterstützte Version {payload.get('version')}")
    return payload["sim"]


def timestamped_path(directory: Path = SAVE_DIR) -> Path:
    return directory / f"spielstand_{datetime.now():%Y-%m-%d_%H-%M-%S}{SUFFIX}"


def list_saves(directory: Path = SAVE_DIR) -> list[Path]:
    """Save files, newest first."""
    if not directory.is_dir():
        return []
    return sorted(directory.glob(f"*{SUFFIX}"), key=lambda p: p.stat().st_mtime, reverse=True)
