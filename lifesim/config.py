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

    # --- time ---
    ticks_per_day: int = 2400
    days_per_season: int = 4
    night_vision_factor: float = 0.4  # fraction of vision left at darkest night

    # --- food ---
    fruit_regrow_ticks: int = 1500  # base value, scaled by season
    fruit_energy: float = 28.0
    hunger_threshold: float = 0.6  # seek food when energy falls below this fraction of max

    # --- trees ---
    tree_seed_chance_per_day: float = 0.3
    tree_lifespan_days: float = 40.0
    tree_maturity_days: float = 2.0  # saplings bear no fruit before this age

    # --- reproduction & evolution ---
    mate_energy_threshold: float = 0.7  # both partners need at least this fraction of max energy
    max_population: int = 500  # hard cap to keep the simulation responsive
    mutation_rate: float = 0.1
    mutation_strength: float = 0.08

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "SimConfig":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})
