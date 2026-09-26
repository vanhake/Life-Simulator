"""Minion state, gene-derived traits and the phase-2 behaviour (forage / mate / wander)."""

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
    SEEK_MATE = "Partner suchen"


class DeathCause(Enum):
    STARVATION = "Verhungert"
    OLD_AGE = "Altersschwäche"


def lerp(lo: float, hi: float, t: float) -> float:
    return lo + (hi - lo) * t


# Energy the body burns per tick just by existing, and per tile travelled.
BASE_DRAIN = 0.02
MOVE_DRAIN_PER_TILE = 0.25
EAT_RANGE = 0.6
MATE_RANGE = 1.0


@dataclass(frozen=True)
class Traits:
    """Real-valued traits derived once from the genome. Durations are in days."""

    speed: float  # tiles per tick on cost-1 terrain
    max_energy: float
    vision: float  # tiles, in daylight
    idle_drain: float  # energy per tick
    move_drain: float  # energy per tile travelled
    digestion: float  # multiplier on fruit energy
    size: float  # visual radius in tiles when fully grown
    lifespan_days: float
    maturity_days: float  # long-lived minions mature later
    mate_cooldown_days: float
    child_cost: float  # fraction of own max energy given to each child

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
            lifespan_days=lerp(6.0, 14.0, g["lifespan"]),
            maturity_days=lerp(1.2, 2.4, g["lifespan"]),
            mate_cooldown_days=lerp(1.5, 0.5, g["fertility"]),
            child_cost=lerp(0.2, 0.35, g["fertility"]),
        )


@dataclass(eq=False)
class Minion:
    id: int
    x: float
    y: float
    genome: Genome
    generation: int = 0
    parents: tuple[int, int] | None = None
    age: int = 0
    max_age: int = 10**9  # ticks; set by the simulation from traits and ticks_per_day
    maturity: int = 0  # ticks
    traits: Traits = field(init=False)
    energy: float = field(init=False)
    alive: bool = True
    death_cause: DeathCause | None = None
    action: Action = Action.WANDER
    target: tuple[float, float] | None = None
    target_tree: "Tree | None" = None
    target_mate: "Minion | None" = None
    mate_cooldown: int = 0
    heading: float = 0.0
    fruits_eaten: int = 0
    children: int = 0

    def __post_init__(self) -> None:
        self.traits = Traits.from_genome(self.genome)
        self.energy = self.traits.max_energy * 0.8

    @property
    def energy_frac(self) -> float:
        return self.energy / self.traits.max_energy

    @property
    def is_adult(self) -> bool:
        return self.age >= self.maturity

    @property
    def growth(self) -> float:
        """0.5 at birth, 1.0 once mature; used for drawing."""
        if self.maturity <= 0:
            return 1.0
        return min(1.0, 0.5 + 0.5 * self.age / self.maturity)

    def vision(self, sim: "Simulation") -> float:
        return self.traits.vision * sim.vision_factor

    def can_mate(self, sim: "Simulation") -> bool:
        return (
            self.alive
            and self.is_adult
            and self.mate_cooldown <= 0
            and self.energy_frac >= sim.config.mate_energy_threshold
        )

    def is_close_kin(self, other: "Minion") -> bool:
        """Parents, children and siblings (incl. half-siblings) do not mate."""
        if self.parents and other.id in self.parents:
            return True
        if other.parents and self.id in other.parents:
            return True
        return bool(self.parents and other.parents and set(self.parents) & set(other.parents))

    # ------------------------------------------------------------------ decision

    def think(self, sim: "Simulation") -> None:
        vision = self.vision(sim)

        if self.energy_frac < sim.config.hunger_threshold:
            self.target_mate = None
            if self.target_tree is None or not self.target_tree.has_fruit:
                self.target_tree = self._find_fruit(sim, vision)
            if self.target_tree is not None:
                self.action = Action.SEEK_FOOD
                self.target = (self.target_tree.x, self.target_tree.y)
                return
        else:
            self.target_tree = None

        if self.can_mate(sim) and len(sim.minions) < sim.config.max_population:
            mate = self.target_mate
            if mate is None or not mate.can_mate(sim):
                mate = self._find_mate(sim, vision)
            self.target_mate = mate
            if mate is not None:
                self.action = Action.SEEK_MATE
                self.target = (mate.x, mate.y)
                return
        else:
            self.target_mate = None

        if self.action is not Action.WANDER:
            self.target = None
        self.action = Action.WANDER
        if self.target is None or self._reached(self.target, 0.3):
            self.target = self._random_destination(sim.terrain, sim.rng, vision)

    def _find_fruit(self, sim: "Simulation", vision: float) -> "Tree | None":
        best, best_d = None, vision
        for tree in sim.forest.index.query_radius(self.x, self.y, vision):
            if not tree.has_fruit:
                continue
            d = math.hypot(tree.x - self.x, tree.y - self.y)
            if d <= best_d:
                best, best_d = tree, d
        return best

    def _find_mate(self, sim: "Simulation", vision: float) -> "Minion | None":
        best, best_d = None, vision
        for other in sim.minion_index.query_radius(self.x, self.y, vision):
            if other is self or not other.can_mate(sim) or self.is_close_kin(other):
                continue
            d = math.hypot(other.x - self.x, other.y - self.y)
            if d <= best_d:
                best, best_d = other, d
        return best

    def _random_destination(
        self, terrain, rng: random.Random, vision: float
    ) -> tuple[float, float] | None:
        # Keep roughly the current heading so wandering looks purposeful rather than jittery.
        for _ in range(8):
            self.heading += rng.uniform(-1.2, 1.2)
            r = rng.uniform(2.0, max(2.0, vision))
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
        mate = self.target_mate
        if mate is not None and self._reached((mate.x, mate.y), MATE_RANGE):
            return  # wait for the simulation to resolve the mating
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
                self.target_mate = None
                self.heading += math.pi / 2
                return
        moved = math.hypot(nx - self.x, ny - self.y)
        if moved > 1e-9:
            self.heading = math.atan2(ny - self.y, nx - self.x)
        self.x, self.y = nx, ny
        self.energy -= moved * self.traits.move_drain

    def metabolise(self) -> None:
        self.age += 1
        if self.mate_cooldown > 0:
            self.mate_cooldown -= 1
        self.energy -= self.traits.idle_drain
        if self.energy <= 0:
            self.energy = 0
            self.die(DeathCause.STARVATION)
        elif self.age >= self.max_age:
            self.die(DeathCause.OLD_AGE)

    def die(self, cause: DeathCause) -> None:
        self.alive = False
        self.death_cause = cause
        self.target_mate = None
