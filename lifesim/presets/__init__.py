"""Presets: named sets of settings stored as JSON.

Built-in presets live next to this module; presets saved by the user go to ./presets.
A preset only lists the values that differ from the defaults, under "werte".
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, fields
from pathlib import Path

from lifesim.config import SimConfig

BUILTIN_DIR = Path(__file__).parent
USER_DIR = Path("presets")
ORDER = ("standard", "paradies", "hungersnot", "raubtierwelt", "schnelle_evolution", "grosse_welt")


class PresetError(Exception):
    pass


@dataclass(frozen=True)
class Preset:
    name: str  # file name without extension
    title: str
    description: str
    values: dict
    builtin: bool

    def config(self, seed: int | None = None) -> SimConfig:
        cfg = SimConfig.from_dict({**SimConfig().to_dict(), **self.values})
        if seed is not None:
            cfg.seed = seed
        return cfg


def _read(path: Path, builtin: bool) -> Preset:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise PresetError(f"{path.name}: {e}") from e
    known = {f.name for f in fields(SimConfig)}
    values = data.get("werte", {})
    unknown = set(values) - known
    if unknown:
        raise PresetError(f"{path.name}: unbekannte Einstellungen {sorted(unknown)}")
    return Preset(path.stem, data.get("titel", path.stem), data.get("beschreibung", ""), values, builtin)


def list_presets(user_dir: Path = USER_DIR) -> list[Preset]:
    """Built-in presets in their intended order, then the user's own, alphabetically."""
    builtin = {p.stem: _read(p, True) for p in BUILTIN_DIR.glob("*.json")}
    presets = [builtin.pop(n) for n in ORDER if n in builtin] + sorted(builtin.values(), key=lambda p: p.name)
    if user_dir.is_dir():
        for path in sorted(user_dir.glob("*.json")):
            try:
                presets.append(_read(path, False))
            except PresetError:
                continue  # a broken user file must not break the list
    return presets


def get(name: str, user_dir: Path = USER_DIR) -> Preset:
    for p in list_presets(user_dir):
        if p.name == name:
            return p
    raise PresetError(f"Voreinstellung '{name}' nicht gefunden")


def slug(title: str) -> str:
    table = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue"})
    s = re.sub(r"[^a-z0-9]+", "_", title.translate(table).lower()).strip("_")
    return s or "eigene"


def save_user_preset(title: str, config: SimConfig, user_dir: Path = USER_DIR) -> Path:
    """Store the values that differ from the defaults (the seed is not part of a preset)."""
    defaults = SimConfig().to_dict()
    values = {k: v for k, v in config.to_dict().items() if k != "seed" and v != defaults[k]}
    user_dir.mkdir(parents=True, exist_ok=True)
    path = user_dir / f"{slug(title)}.json"
    data = {"titel": title, "beschreibung": "Eigene Voreinstellung", "werte": values}
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
