"""Fruit trees. Each tree carries at most one fruit which regrows after being eaten."""

from __future__ import annotations

import random
from dataclasses import dataclass

from lifesim.core.spatial import SpatialHash
from lifesim.world.terrain import TREE_FACTOR, Terrain, TerrainMap


@dataclass(eq=False)
class Tree:
    id: int
    x: float
    y: float
    has_fruit: bool = True
    regrow_timer: int = 0


class Forest:
    def __init__(self) -> None:
        self.trees: list[Tree] = []
        self.index: SpatialHash[Tree] = SpatialHash(cell_size=8.0)
        self._next_id = 0

    def add(self, x: float, y: float, has_fruit: bool = True) -> Tree:
        tree = Tree(self._next_id, x, y, has_fruit)
        self._next_id += 1
        self.trees.append(tree)
        self.index.insert(tree, x, y)
        return tree

    def populate(self, terrain: TerrainMap, density: float, rng: random.Random) -> None:
        for ty in range(terrain.height):
            for tx in range(terrain.width):
                factor = TREE_FACTOR[Terrain(int(terrain.tiles[ty, tx]))]
                if factor > 0 and rng.random() < density * factor:
                    self.add(tx + 0.5, ty + 0.5, has_fruit=rng.random() < 0.7)

    def eat(self, tree: Tree, regrow_ticks: int) -> bool:
        if not tree.has_fruit:
            return False
        tree.has_fruit = False
        tree.regrow_timer = regrow_ticks
        return True

    def update(self) -> None:
        for tree in self.trees:
            if not tree.has_fruit:
                tree.regrow_timer -= 1
                if tree.regrow_timer <= 0:
                    tree.has_fruit = True

    def fruit_count(self) -> int:
        return sum(1 for t in self.trees if t.has_fruit)
