"""Terrain types and procedural terrain generation."""

from __future__ import annotations

from enum import IntEnum

import numpy as np

from lifesim.world.noise import fractal_noise


class Terrain(IntEnum):
    GRASS = 0
    FOREST = 1
    SWAMP = 2
    MOUNTAIN = 3
    ROCK = 4


# Movement cost multiplier (higher = slower). None = impassable.
MOVE_COST: dict[Terrain, float | None] = {
    Terrain.GRASS: 1.0,
    Terrain.FOREST: 1.5,
    Terrain.SWAMP: 2.5,
    Terrain.MOUNTAIN: 3.0,
    Terrain.ROCK: None,
}

# Relative likelihood of a tree growing on a tile of this terrain.
TREE_FACTOR: dict[Terrain, float] = {
    Terrain.GRASS: 0.6,
    Terrain.FOREST: 3.0,
    Terrain.SWAMP: 0.8,
    Terrain.MOUNTAIN: 0.2,
    Terrain.ROCK: 0.0,
}

NAMES_DE: dict[Terrain, str] = {
    Terrain.GRASS: "Wiese",
    Terrain.FOREST: "Wald",
    Terrain.SWAMP: "Sumpf",
    Terrain.MOUNTAIN: "Berg",
    Terrain.ROCK: "Fels",
}


_INF = float("inf")


class TerrainMap:
    def __init__(self, tiles: np.ndarray) -> None:
        self.tiles = tiles  # shape (height, width), dtype uint8
        self.height, self.width = tiles.shape
        cost = np.full(tiles.shape, np.inf)
        for t, c in MOVE_COST.items():
            if c is not None:
                cost[tiles == t] = c
        self.cost = cost
        # Plain nested lists: scalar lookups are far cheaper than numpy indexing in hot loops.
        self._cost_rows: list[list[float]] = cost.tolist()

    def in_bounds(self, x: float, y: float) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def at(self, x: float, y: float) -> Terrain:
        return Terrain(int(self.tiles[int(y), int(x)]))

    def passable(self, x: float, y: float) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height and self._cost_rows[int(y)][int(x)] != _INF

    def move_cost(self, x: float, y: float) -> float:
        return self._cost_rows[int(y)][int(x)]


def generate_terrain(width: int, height: int, rng: np.random.Generator) -> TerrainMap:
    elevation = fractal_noise(width, height, rng, base_scale=max(width, height) / 4)
    moisture = fractal_noise(width, height, rng, base_scale=max(width, height) / 5)

    tiles = np.full((height, width), Terrain.GRASS, dtype=np.uint8)
    tiles[moisture > 0.55] = Terrain.FOREST
    tiles[(moisture > 0.6) & (elevation < 0.35)] = Terrain.SWAMP
    tiles[elevation > 0.75] = Terrain.MOUNTAIN
    tiles[elevation > 0.88] = Terrain.ROCK
    return TerrainMap(tiles)
