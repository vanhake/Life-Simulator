"""Fruit trees.

Each tree carries at most one fruit which regrows after being eaten. Trees age, die,
and spread seeds into nearby free tiles. Every terrain type has a carrying capacity for
trees, so forests stay denser than meadows and the total stays bounded.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lifesim.core.spatial import SpatialHash
from lifesim.world.terrain import TREE_FACTOR, Terrain, TerrainMap

if TYPE_CHECKING:
    from lifesim.config import SimConfig
    from lifesim.core.clock import Clock

SEED_MIN_DIST = 1.0
SEED_MAX_DIST = 4.0
# How far the tree count per terrain may grow beyond the expected initial count.
CAPACITY_HEADROOM = 1.2


@dataclass(eq=False)
class Tree:
    id: int
    x: float
    y: float
    terrain: Terrain
    has_fruit: bool = True
    regrow_timer: float = 0.0
    age: int = 0
    max_age: int = 0
    maturity: int = 0
    alive: bool = True

    @property
    def tile(self) -> tuple[int, int]:
        return int(self.x), int(self.y)

    @property
    def is_sapling(self) -> bool:
        return self.age < self.maturity


class Forest:
    def __init__(self) -> None:
        self.trees: list[Tree] = []
        self.index: SpatialHash[Tree] = SpatialHash(cell_size=8.0)
        self._occupied: set[tuple[int, int]] = set()
        self._per_terrain: dict[Terrain, int] = {t: 0 for t in Terrain}
        self.capacity: dict[Terrain, float] = {t: float("inf") for t in Terrain}
        self._next_id = 0
        self.born = 0
        self.died = 0

    # ------------------------------------------------------------------ creation

    def add(
        self,
        tx: int,
        ty: int,
        terrain: Terrain,
        *,
        has_fruit: bool = True,
        age: int = 0,
        max_age: int = 10**9,
        maturity: int = 0,
    ) -> Tree | None:
        if (tx, ty) in self._occupied:
            return None
        tree = Tree(
            self._next_id, tx + 0.5, ty + 0.5, terrain, has_fruit, 0.0, age, max_age, maturity
        )
        if not has_fruit:
            tree.regrow_timer = max(1, maturity - age)
        self._next_id += 1
        self.trees.append(tree)
        self.index.insert(tree, tree.x, tree.y)
        self._occupied.add((tx, ty))
        self._per_terrain[terrain] += 1
        return tree

    def populate(self, terrain: TerrainMap, config: "SimConfig", rng: random.Random) -> None:
        tpd = config.ticks_per_day
        maturity = int(config.tree_maturity_days * tpd)
        for t in Terrain:
            tiles = int((terrain.tiles == t).sum())
            self.capacity[t] = tiles * config.tree_density * TREE_FACTOR[t] * CAPACITY_HEADROOM
        for ty in range(terrain.height):
            for tx in range(terrain.width):
                kind = Terrain(int(terrain.tiles[ty, tx]))
                factor = TREE_FACTOR[kind]
                if factor > 0 and rng.random() < config.tree_density * factor:
                    max_age = self._roll_max_age(config, rng)
                    # Spread initial ages so the founding forest does not die all at once.
                    self.add(
                        tx,
                        ty,
                        kind,
                        has_fruit=rng.random() < 0.7,
                        age=rng.randrange(maturity, max(maturity + 1, max_age)),
                        max_age=max_age,
                        maturity=maturity,
                    )

    @staticmethod
    def _roll_max_age(config: "SimConfig", rng: random.Random) -> int:
        return int(config.tree_lifespan_days * config.ticks_per_day * rng.uniform(0.6, 1.4))

    # ------------------------------------------------------------------ fruit

    def eat(self, tree: Tree, regrow_ticks: int) -> bool:
        if not tree.has_fruit or not tree.alive:
            return False
        tree.has_fruit = False
        tree.regrow_timer = regrow_ticks
        return True

    def fruit_count(self) -> int:
        return sum(1 for t in self.trees if t.has_fruit)

    # ------------------------------------------------------------------ tick

    def update(
        self,
        clock: "Clock",
        config: "SimConfig",
        terrain: TerrainMap,
        rng: random.Random,
        ticks: int = 1,
    ) -> None:
        """Advance every tree by `ticks` ticks."""
        fruit_factor = clock.fruit_factor * ticks
        seed_chance = (
            config.tree_seed_chance_per_day / clock.ticks_per_day * clock.seed_factor * ticks
        )
        seeds: list[Tree] = []
        died = False

        for tree in self.trees:
            tree.age += ticks
            if tree.age >= tree.max_age:
                tree.alive = False
                tree.has_fruit = False
                died = True
                continue
            if not tree.has_fruit:
                # Saplings grow at a constant pace; fruit regrowth follows the season.
                tree.regrow_timer -= ticks if tree.is_sapling else fruit_factor
                if tree.regrow_timer <= 0:
                    tree.has_fruit = True
            if seed_chance > 0 and not tree.is_sapling and rng.random() < seed_chance:
                seeds.append(tree)

        if died:
            for tree in self.trees:
                if not tree.alive:
                    self.index.remove(tree, tree.x, tree.y)
                    self._occupied.discard(tree.tile)
                    self._per_terrain[tree.terrain] -= 1
                    self.died += 1
            self.trees = [t for t in self.trees if t.alive]

        for parent in seeds:
            self._try_seed(parent, config, terrain, rng)

    def _try_seed(
        self, parent: Tree, config: "SimConfig", terrain: TerrainMap, rng: random.Random
    ) -> None:
        angle = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(SEED_MIN_DIST, SEED_MAX_DIST)
        x, y = parent.x + math.cos(angle) * r, parent.y + math.sin(angle) * r
        if not terrain.passable(x, y):
            return
        tx, ty = int(x), int(y)
        if (tx, ty) in self._occupied:
            return
        kind = terrain.at(x, y)
        # Seeds take root more easily on fertile terrain, and only while it has room left.
        if rng.random() >= TREE_FACTOR[kind] / max(TREE_FACTOR.values()):
            return
        if self._per_terrain[kind] >= self.capacity[kind]:
            return
        maturity = int(config.tree_maturity_days * config.ticks_per_day)
        if self.add(
            tx, ty, kind, has_fruit=False, max_age=self._roll_max_age(config, rng), maturity=maturity
        ):
            self.born += 1
