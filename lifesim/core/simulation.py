"""The simulation: owns the world state and advances it one fixed tick at a time."""

from __future__ import annotations

import random

import numpy as np

from lifesim.agents.genome import GENE_NAMES, Genome
from lifesim.agents.minion import Minion
from lifesim.config import SimConfig
from lifesim.core.spatial import SpatialHash
from lifesim.world.terrain import TerrainMap, generate_terrain
from lifesim.world.trees import Forest

STATS_INTERVAL = 30


class Simulation:
    def __init__(self, config: SimConfig) -> None:
        self.config = config
        self.rng = random.Random(config.seed)
        np_rng = np.random.default_rng(config.seed)

        self.tick = 0
        self.terrain: TerrainMap = generate_terrain(config.map_width, config.map_height, np_rng)
        self.forest = Forest()
        self.forest.populate(self.terrain, config.tree_density, self.rng)

        self.minions: list[Minion] = []
        self.minion_index: SpatialHash[Minion] = SpatialHash(cell_size=8.0)
        self._next_minion_id = 0
        self.deaths = 0
        self.history: list[dict] = []

        for _ in range(config.initial_minions):
            x, y = self.random_passable_point()
            self.spawn_minion(x, y, Genome.random(self.rng))
        self._rebuild_index()
        self._record_stats()

    # ------------------------------------------------------------------ helpers

    def random_passable_point(self) -> tuple[float, float]:
        while True:
            x = self.rng.uniform(0, self.terrain.width)
            y = self.rng.uniform(0, self.terrain.height)
            if self.terrain.passable(x, y):
                return x, y

    def spawn_minion(self, x: float, y: float, genome: Genome, generation: int = 0) -> Minion:
        m = Minion(self._next_minion_id, x, y, genome, generation=generation)
        m.heading = self.rng.uniform(0, 6.283)
        self._next_minion_id += 1
        self.minions.append(m)
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
        self.tick += 1
        self.forest.update()

        for m in self.minions:
            m.think(self)
        for m in self.minions:
            m.act(self)
        for m in self.minions:
            m.metabolise()

        alive = [m for m in self.minions if m.alive]
        self.deaths += len(self.minions) - len(alive)
        self.minions = alive
        self._rebuild_index()

        if self.tick % STATS_INTERVAL == 0:
            self._record_stats()

    def _record_stats(self) -> None:
        n = len(self.minions)
        row: dict = {
            "tick": self.tick,
            "population": n,
            "fruits": self.forest.fruit_count(),
            "trees": len(self.forest.trees),
        }
        for g in GENE_NAMES:
            row[f"gene_{g}"] = sum(m.genome[g] for m in self.minions) / n if n else 0.0
        self.history.append(row)
