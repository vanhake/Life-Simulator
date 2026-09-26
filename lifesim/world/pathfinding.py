"""Grid path finding with terrain costs.

Minions walk in a straight line when nothing blocks it and fall back to A* only when a
rock is in the way, which keeps the per-tick cost low with hundreds of agents.
"""

from __future__ import annotations

import heapq
import math

from lifesim.world.terrain import TerrainMap

SQRT2 = math.sqrt(2.0)
_NEIGHBOURS = (
    (1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
    (1, 1, SQRT2), (1, -1, SQRT2), (-1, 1, SQRT2), (-1, -1, SQRT2),
)  # fmt: skip


def line_clear(terrain: TerrainMap, x0: float, y0: float, x1: float, y1: float) -> bool:
    """True if the straight segment only crosses passable tiles (sampled every 1/3 tile)."""
    d = math.hypot(x1 - x0, y1 - y0)
    steps = max(1, int(d * 3))
    for i in range(1, steps + 1):
        t = i / steps
        if not terrain.passable(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t):
            return False
    return True


def find_path(
    terrain: TerrainMap,
    start: tuple[float, float],
    goal: tuple[float, float],
    max_nodes: int = 1500,
) -> list[tuple[float, float]] | None:
    """A* over tiles. Returns waypoints (tile centres, ending at the exact goal) or None.

    Diagonal moves may not cut the corner of an impassable tile.
    """
    sx, sy = int(start[0]), int(start[1])
    gx, gy = int(goal[0]), int(goal[1])
    if not terrain.passable(gx + 0.5, gy + 0.5):
        return None
    if (sx, sy) == (gx, gy):
        return [goal]

    cost = terrain._cost_rows
    w, h = terrain.width, terrain.height
    inf = math.inf

    def heuristic(x: int, y: int) -> float:
        dx, dy = abs(x - gx), abs(y - gy)
        return (dx + dy) + (SQRT2 - 2) * min(dx, dy)  # octile distance, min cost 1

    open_heap: list[tuple[float, float, int, int]] = [(heuristic(sx, sy), 0.0, sx, sy)]
    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    best_g: dict[tuple[int, int], float] = {(sx, sy): 0.0}
    expanded = 0

    while open_heap:
        _, g, x, y = heapq.heappop(open_heap)
        if (x, y) == (gx, gy):
            return _reconstruct(came_from, (gx, gy), goal)
        if g > best_g.get((x, y), inf):
            continue
        expanded += 1
        if expanded > max_nodes:
            return None
        for dx, dy, step in _NEIGHBOURS:
            nx, ny = x + dx, y + dy
            if not (0 <= nx < w and 0 <= ny < h):
                continue
            c = cost[ny][nx]
            if c == inf:
                continue
            if dx and dy and (cost[y][nx] == inf or cost[ny][x] == inf):
                continue
            # Average of both tiles' costs approximates walking across the border.
            ng = g + step * (c + cost[y][x]) * 0.5
            if ng < best_g.get((nx, ny), inf):
                best_g[(nx, ny)] = ng
                came_from[(nx, ny)] = (x, y)
                heapq.heappush(open_heap, (ng + heuristic(nx, ny), ng, nx, ny))
    return None


def _reconstruct(
    came_from: dict[tuple[int, int], tuple[int, int]],
    end: tuple[int, int],
    goal: tuple[float, float],
) -> list[tuple[float, float]]:
    tiles = [end]
    while tiles[-1] in came_from:
        tiles.append(came_from[tiles[-1]])
    tiles.reverse()
    waypoints = [(tx + 0.5, ty + 0.5) for tx, ty in tiles[1:-1]]
    waypoints.append(goal)
    return waypoints
