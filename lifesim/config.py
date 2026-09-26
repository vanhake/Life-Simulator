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

    # --- predators (a population of their own, without evolution) ---
    initial_predators: int = 4
    max_predators: int = 15
    predator_speed: float = 0.08  # tiles per tick; fast minions can outrun them
    predator_vision: float = 9.0
    predator_max_energy: float = 300.0
    predator_drain: float = 0.05  # energy per tick
    predator_kill_energy: float = 90.0  # energy gained from an adult minion
    predator_lifespan_days: float = 16.0
    predator_breed_energy: float = 0.9  # fraction of max energy needed to breed
    predator_breed_cooldown_days: float = 6.0
    predator_repel_power: float = 1.6  # combined fight power of defenders that drives one off
    predator_immigration: bool = True  # newcomers arrive in spring/summer if all died out

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
