"""Simulation configuration."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields


@dataclass
class SimConfig:
    # --- world (applied on (re)start) ---
    seed: int = 42
    map_width: int = 120
    map_height: int = 80
    initial_minions: int = 60
    tree_density: float = 0.04  # fraction of passable tiles carrying a tree (before terrain factor)

    # --- live tunables ---
    fruit_regrow_ticks: int = 600
    fruit_energy: float = 40.0
    hunger_threshold: float = 0.6  # seek food when energy falls below this fraction of max
    mutation_rate: float = 0.1
    mutation_strength: float = 0.08

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "SimConfig":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})
