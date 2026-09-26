"""Movement shared by minions and predators: planning a route and walking along it.

Classes using the mixin provide the attributes `x`, `y`, `heading` and `path`.
"""

from __future__ import annotations

import math

from lifesim.world.pathfinding import find_path, line_clear
from lifesim.world.terrain import TerrainMap

WAYPOINT_RADIUS = 0.2
FLEE_ANGLES = (0.0, 0.5, -0.5, 1.0, -1.0, 1.6, -1.6)


class Mover:
    x: float
    y: float
    heading: float
    path: list[tuple[float, float]]

    @property
    def target(self) -> tuple[float, float] | None:
        return self.path[-1] if self.path else None

    def go_to(self, terrain: TerrainMap, goal: tuple[float, float]) -> bool:
        """Plan a route: straight if nothing blocks it, A* otherwise."""
        if line_clear(terrain, self.x, self.y, goal[0], goal[1]):
            self.path = [goal]
            return True
        path = find_path(terrain, (self.x, self.y), goal)
        self.path = path or []
        return path is not None

    def flee_from(self, terrain: TerrainMap, threat: tuple[float, float], dist: float) -> bool:
        """Run straight away from `threat`, veering sideways if the way is blocked."""
        away = math.atan2(self.y - threat[1], self.x - threat[0])
        for offset in FLEE_ANGLES:
            a = away + offset
            tx, ty = self.x + math.cos(a) * dist, self.y + math.sin(a) * dist
            if terrain.passable(tx, ty) and line_clear(terrain, self.x, self.y, tx, ty):
                self.path = [(tx, ty)]
                return True
        self.path = []
        return False

    def advance(self, terrain: TerrainMap, speed: float) -> tuple[float, bool]:
        """Walk along the path for one tick. Returns (distance moved, blocked)."""
        budget = speed / terrain.move_cost(self.x, self.y)
        moved = 0.0
        while budget > 1e-9 and self.path:
            wx, wy = self.path[0]
            dx, dy = wx - self.x, wy - self.y
            d = math.hypot(dx, dy)
            if d <= WAYPOINT_RADIUS and len(self.path) > 1:
                self.path.pop(0)
                continue
            step = min(d, budget)
            if step <= 1e-9:
                self.path.pop(0)
                break
            nx, ny = self.x + dx / d * step, self.y + dy / d * step
            if not terrain.passable(nx, ny):
                # The world changed or we clipped a corner: the caller should re-plan.
                self.path.clear()
                self.heading += math.pi / 2
                return moved, True
            self.heading = math.atan2(dy, dx)
            self.x, self.y = nx, ny
            moved += step
            budget -= step
            if step >= d:
                self.path.pop(0)
        return moved, False
