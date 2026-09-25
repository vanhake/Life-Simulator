"""Minion state, gene-derived traits and the phase-1 behaviour (forage / wander)."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from lifesim.agents.genome import Genome

if TYPE_CHECKING:
    from lifesim.core.simulation import Simulation
    from lifesim.world.trees import Tree


class Action(Enum):
    WANDER = "Umherstreifen"
    SEEK_FOOD = "Futter suchen"
    EAT = "Essen"


def lerp(lo: float, hi: float, t: float) -> float:
    return lo + (hi - lo) * t


# Energy the body burns per tick just by existing, and per tile travelled.
BASE_DRAIN = 0.02
MOVE_DRAIN_PER_TILE = 0.25
EAT_RANGE = 0.6


@dataclass(frozen=True)
class Traits:
    """Real-valued traits derived once from the genome."""

    speed: float  # tiles per tick on cost-1 terrain
    max_energy: float
    vision: float  # tiles
    idle_drain: float  # energy per tick
    move_drain: float  # energy per tile travelled
    digestion: float  # multiplier on fruit energy
    size: float  # visual radius in tiles

    @classmethod
    def from_genome(cls, g: Genome) -> "Traits":
        return cls(
            speed=lerp(0.03, 0.12, g["speed"]),
            max_energy=lerp(60.0, 160.0, g["max_energy"]),
            vision=lerp(4.0, 14.0, g["vision"]),
            idle_drain=BASE_DRAIN
            * (0.6 + 0.8 * g["strength"] + 0.6 * g["metabolism"] + 0.2 * g["vision"]),
            # Fast movers pay quadratically; heavy energy stores make walking more expensive.
            move_drain=MOVE_DRAIN_PER_TILE
            * (0.5 + 1.5 * g["speed"] ** 2 + 0.5 * g["max_energy"] + 0.4 * g["strength"]),
            digestion=lerp(0.8, 1.2, g["metabolism"]),
            size=lerp(0.25, 0.45, g["strength"]),
        )


@dataclass(eq=False)
class Minion:
    id: int
    x: float
    y: float
    genome: Genome
    traits: Traits = field(init=False)
    energy: float = field(init=False)
    age: int = 0
    generation: int = 0
    alive: bool = True
    action: Action = Action.WANDER
    target: tuple[float, float] | None = None
    target_tree: "Tree | None" = None
    heading: float = 0.0
    fruits_eaten: int = 0

    def __post_init__(self) -> None:
        self.traits = Traits.from_genome(self.genome)
        self.energy = self.traits.max_energy * 0.8

    @property
    def energy_frac(self) -> float:
        return self.energy / self.traits.max_energy

    # ------------------------------------------------------------------ decision

    def think(self, sim: "Simulation") -> None:
        hungry = self.energy_frac < sim.config.hunger_threshold
        if hungry:
            if self.target_tree is None or not self.target_tree.has_fruit:
                self.target_tree = self._find_fruit(sim)
            if self.target_tree is not None:
                self.action = Action.SEEK_FOOD
                self.target = (self.target_tree.x, self.target_tree.y)
                return
        else:
            self.target_tree = None

        self.action = Action.WANDER
        if self.target is None or self._reached(self.target, 0.3):
            self.target = self._random_destination(sim.terrain, sim.rng)

    def _find_fruit(self, sim: "Simulation") -> "Tree | None":
        best, best_d = None, self.traits.vision
        for tree in sim.forest.index.query_radius(self.x, self.y, self.traits.vision):
            if not tree.has_fruit:
                continue
            d = math.hypot(tree.x - self.x, tree.y - self.y)
            if d <= best_d:
                best, best_d = tree, d
        return best

    def _random_destination(self, terrain, rng: random.Random) -> tuple[float, float] | None:
        # Keep roughly the current heading so wandering looks purposeful rather than jittery.
        for _ in range(8):
            self.heading += rng.uniform(-1.2, 1.2)
            r = rng.uniform(2.0, self.traits.vision)
            tx = self.x + math.cos(self.heading) * r
            ty = self.y + math.sin(self.heading) * r
            if terrain.passable(tx, ty):
                return tx, ty
        return None

    def _reached(self, point: tuple[float, float], radius: float) -> bool:
        return math.hypot(point[0] - self.x, point[1] - self.y) <= radius

    # ------------------------------------------------------------------ acting

    def act(self, sim: "Simulation") -> None:
        tree = self.target_tree
        if tree is not None and self._reached((tree.x, tree.y), EAT_RANGE):
            if sim.forest.eat(tree, sim.config.fruit_regrow_ticks):
                self.action = Action.EAT
                self.energy = min(
                    self.traits.max_energy,
                    self.energy + sim.config.fruit_energy * self.traits.digestion,
                )
                self.fruits_eaten += 1
            self.target_tree = None
            self.target = None
            return
        if self.target is not None:
            self._move_towards(self.target, sim)

    def _move_towards(self, point: tuple[float, float], sim: "Simulation") -> None:
        terrain = sim.terrain
        dx, dy = point[0] - self.x, point[1] - self.y
        d = math.hypot(dx, dy)
        if d < 1e-6:
            return
        step = min(d, self.traits.speed / terrain.move_cost(self.x, self.y))
        nx, ny = self.x + dx / d * step, self.y + dy / d * step

        # Slide along impassable tiles by trying each axis on its own.
        if not terrain.passable(nx, ny):
            if terrain.passable(nx, self.y):
                ny = self.y
            elif terrain.passable(self.x, ny):
                nx = self.x
            else:
                self.target = None
                self.target_tree = None
                self.heading += math.pi / 2
                return
        moved = math.hypot(nx - self.x, ny - self.y)
        if moved > 1e-9:
            self.heading = math.atan2(ny - self.y, nx - self.x)
        self.x, self.y = nx, ny
        self.energy -= moved * self.traits.move_drain

    def metabolise(self) -> None:
        self.age += 1
        self.energy -= self.traits.idle_drain
        if self.energy <= 0:
            self.energy = 0
            self.alive = False
