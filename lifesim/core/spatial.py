"""Uniform-grid spatial hash for fast neighbour queries."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Generic, Iterator, TypeVar

T = TypeVar("T")


class SpatialHash(Generic[T]):
    def __init__(self, cell_size: float = 8.0) -> None:
        self.cell_size = cell_size
        self._cells: dict[tuple[int, int], list[T]] = defaultdict(list)

    def _key(self, x: float, y: float) -> tuple[int, int]:
        return int(x // self.cell_size), int(y // self.cell_size)

    def clear(self) -> None:
        self._cells.clear()

    def insert(self, obj: T, x: float, y: float) -> None:
        self._cells[self._key(x, y)].append(obj)

    def remove(self, obj: T, x: float, y: float) -> None:
        cell = self._cells.get(self._key(x, y))
        if cell is not None and obj in cell:
            cell.remove(obj)

    def query_radius(self, x: float, y: float, radius: float) -> Iterator[T]:
        """Yield every object whose cell overlaps the query circle.

        Callers must still check the exact distance.
        """
        cs = self.cell_size
        x0, x1 = int((x - radius) // cs), int((x + radius) // cs)
        y0, y1 = int((y - radius) // cs), int((y + radius) // cs)
        for cx in range(x0, x1 + 1):
            for cy in range(y0, y1 + 1):
                cell = self._cells.get((cx, cy))
                if cell:
                    yield from cell


def dist(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(ax - bx, ay - by)
