"""The simulation: owns the world state and advances it one fixed tick at a time."""

from __future__ import annotations

import math
import random
from collections import Counter

import numpy as np

from lifesim.agents.genome import GENE_NAMES, Genome
from lifesim.agents.lineage import Lineage
from lifesim.agents.minion import MATE_RANGE, Action, DeathCause, Minion
from lifesim.config import SimConfig
from lifesim.core.clock import Clock
from lifesim.core.spatial import SpatialHash
from lifesim.world.terrain import TerrainMap, generate_terrain
from lifesim.world.trees import Forest

STATS_INTERVAL = 30


class Simulation:
    def __init__(self, config: SimConfig) -> None:
        self.config = config
        self.rng = random.Random(config.seed)
        np_rng = np.random.default_rng(config.seed)

        self.clock = Clock(config.ticks_per_day, config.days_per_season)
        self.vision_factor = 1.0  # daylight-dependent multiplier on vision, updated each tick
        self.terrain: TerrainMap = generate_terrain(config.map_width, config.map_height, np_rng)
        self.forest = Forest()
        self.forest.populate(self.terrain, config, self.rng)

        self.minions: list[Minion] = []
        self.minion_index: SpatialHash[Minion] = SpatialHash(cell_size=8.0)
        self.lineage = Lineage()
        self._next_minion_id = 0
        self.births = 0
        self.deaths: Counter[DeathCause] = Counter()
        self.history: list[dict] = []

        for _ in range(config.initial_minions):
            x, y = self.random_passable_point()
            m = self.spawn_minion(x, y, Genome.random(self.rng))
            # Founders start as young adults of varied age so they do not all die together.
            m.age = int(self.rng.uniform(1.0, 1.6) * m.maturity)
        self._rebuild_index()
        self._record_stats()

    @property
    def tick(self) -> int:
        return self.clock.tick

    # ------------------------------------------------------------------ helpers

    def random_passable_point(self) -> tuple[float, float]:
        while True:
            x = self.rng.uniform(0, self.terrain.width)
            y = self.rng.uniform(0, self.terrain.height)
            if self.terrain.passable(x, y):
                return x, y

    def spawn_minion(
        self,
        x: float,
        y: float,
        genome: Genome,
        generation: int = 0,
        parents: tuple[int, int] | None = None,
    ) -> Minion:
        m = Minion(self._next_minion_id, x, y, genome, generation=generation, parents=parents)
        tpd = self.config.ticks_per_day
        m.max_age = int(m.traits.lifespan_days * tpd * self.rng.uniform(0.9, 1.1))
        m.maturity = int(m.traits.maturity_days * tpd)
        m.heading = self.rng.uniform(0, 2 * math.pi)
        self._next_minion_id += 1
        self.minions.append(m)
        self.lineage.birth(m.id, parents, generation, self.tick)
        return m

    def minion_at(self, x: float, y: float, radius: float = 0.8) -> Minion | None:
        best, best_d = None, radius
        for m in self.minion_index.query_radius(x, y, radius):
            if not m.alive:
                continue
            d = ((m.x - x) ** 2 + (m.y - y) ** 2) ** 0.5
            if d <= best_d:
                best, best_d = m, d
        return best

    def _rebuild_index(self) -> None:
        self.minion_index.clear()
        for m in self.minions:
            self.minion_index.insert(m, m.x, m.y)

    # ------------------------------------------------------------------ tick

    def step(self) -> None:
        self.clock.tick += 1
        night = self.config.night_vision_factor
        self.vision_factor = night + (1.0 - night) * self.clock.daylight
        self.forest.update(self.clock, self.config, self.terrain, self.rng)

        for m in self.minions:
            m.think(self)
        for m in self.minions:
            m.act(self)
        self._resolve_mating()
        for m in self.minions:
            m.metabolise()

        alive = []
        for m in self.minions:
            if m.alive:
                alive.append(m)
            else:
                self.deaths[m.death_cause] += 1
                self.lineage.death(m.id, self.tick, m.death_cause.value)
        self.minions = alive
        self._rebuild_index()

        if self.tick % STATS_INTERVAL == 0:
            self._record_stats()

    def _resolve_mating(self) -> None:
        # Iterate over a snapshot: newborns are appended to self.minions.
        for m in list(self.minions):
            mate = m.target_mate
            if m.action is not Action.SEEK_MATE or mate is None:
                continue
            if len(self.minions) >= self.config.max_population:
                return
            if math.hypot(mate.x - m.x, mate.y - m.y) > MATE_RANGE:
                continue
            if not (m.can_mate(self) and mate.can_mate(self)) or m.is_close_kin(mate):
                continue
            self.reproduce(m, mate)

    def reproduce(self, a: Minion, b: Minion) -> Minion:
        cfg = self.config
        genome = Genome.crossover(a.genome, b.genome, self.rng).mutated(
            self.rng, cfg.mutation_rate, cfg.mutation_strength
        )
        x, y = (a.x + b.x) / 2, (a.y + b.y) / 2
        if not self.terrain.passable(x, y):
            x, y = a.x, a.y
        child = self.spawn_minion(
            x, y, genome, generation=max(a.generation, b.generation) + 1, parents=(a.id, b.id)
        )

        # Each parent hands over part of its energy; the child starts with the sum.
        gift = 0.0
        tpd = cfg.ticks_per_day
        for parent in (a, b):
            cost = parent.traits.child_cost * parent.traits.max_energy
            parent.energy -= cost
            gift += cost
            parent.mate_cooldown = int(parent.traits.mate_cooldown_days * tpd)
            parent.children += 1
            parent.target_mate = None
            parent.target = None
            parent.action = Action.WANDER
        child.energy = min(child.traits.max_energy, gift)
        self.births += 1
        return child

    # ------------------------------------------------------------------ stats

    def _record_stats(self) -> None:
        n = len(self.minions)
        row: dict = {
            "tick": self.tick,
            "day": self.clock.day,
            "season": self.clock.season,
            "population": n,
            "births": self.births,
            "deaths_starvation": self.deaths[DeathCause.STARVATION],
            "deaths_old_age": self.deaths[DeathCause.OLD_AGE],
            "fruits": self.forest.fruit_count(),
            "trees": len(self.forest.trees),
            "mean_generation": sum(m.generation for m in self.minions) / n if n else 0.0,
            "max_generation": max((m.generation for m in self.minions), default=0),
        }
        for g in GENE_NAMES:
            row[f"gene_{g}"] = sum(m.genome[g] for m in self.minions) / n if n else 0.0
        self.history.append(row)
