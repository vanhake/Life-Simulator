"""Predators: a population of their own that hunts minions.

Predators do not evolve; all of them share the traits set in the configuration. They
hunt mostly at night (when minions see poorly), rest while digesting, breed when well
fed and starve when prey is scarce, which produces predator-prey cycles. A group of
minions standing together can drive a predator off.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from lifesim.agents.brain import Action
from lifesim.agents.minion import SOCIAL_RADIUS, DeathCause, Minion
from lifesim.agents.movement import Mover
from lifesim.social.interactions import fight_power

if TYPE_CHECKING:
    from lifesim.core.simulation import Simulation

THINK_INTERVAL = 6
CATCH_RANGE = 0.7
MOVE_DRAIN_PER_TILE = 0.1
REST_DRAIN_FACTOR = 0.6
HUNGRY_BELOW = 0.85  # hunt at night below this energy fraction ...
STARVING_BELOW = 0.5  # ... and also by day below this one
CHASE_GIVE_UP_DAYS = 0.1
DIGEST_DAYS = 0.15
RETREAT_DAYS = 0.1
RETREAT_COST = 15.0
DEFENCE_STATUS = 0.1
DEFENCE_BOND = 0.15
VICTIM_SCARE_COST = 0.1  # fraction of max energy a victim loses even if rescued
SLEEPING_HELPER_WEIGHT = 0.5
WINTER_DRAIN_FACTOR = 1.5  # the cold makes lean times harder for predators too


class PredatorState(Enum):
    WANDER = "Umherstreifen"
    HUNT = "Jagen"
    REST = "Ruhen"
    RETREAT = "Zurückweichen"


@dataclass(eq=False)
class Predator(Mover):
    id: int
    x: float
    y: float
    energy: float
    max_energy: float
    max_age: int
    age: int = 0
    alive: bool = True
    state: PredatorState = PredatorState.WANDER
    heading: float = 0.0
    path: list[tuple[float, float]] = field(default_factory=list)
    prey: Minion | None = None
    chase_ticks: int = 0
    busy_ticks: int = 0  # remaining ticks of digesting or retreating
    breed_cooldown: int = 0
    kills: int = 0
    _moved: float = 0.0

    @property
    def energy_frac(self) -> float:
        return self.energy / self.max_energy

    @property
    def is_dangerous(self) -> bool:
        """Resting and retreating predators are less of a worry than prowling ones."""
        return self.state in (PredatorState.HUNT, PredatorState.WANDER)

    # ------------------------------------------------------------------ decision

    def think(self, sim: "Simulation") -> None:
        if self.busy_ticks > 0:
            return  # digesting or retreating
        hunting = self.state is PredatorState.HUNT and self.prey is not None
        if not hunting and (sim.tick + self.id) % THINK_INTERVAL:
            return
        if self.state is PredatorState.RETREAT:
            self.state = PredatorState.WANDER

        hungry = self.energy_frac < (HUNGRY_BELOW if sim.clock.is_night else STARVING_BELOW)
        if not hungry:
            self.prey = None
            self._wander(sim)
            return

        if self.prey is None or not self.prey.alive:
            self.prey = self._choose_prey(sim)
            self.chase_ticks = 0
        if self.prey is None:
            self._wander(sim)
            return
        self.state = PredatorState.HUNT

    def _choose_prey(self, sim: "Simulation") -> Minion | None:
        """Prefer close, young and isolated prey."""
        vision = sim.config.predator_vision
        best, best_score = None, math.inf
        for m in sim.minion_index.query_radius(self.x, self.y, vision):
            if not m.alive:
                continue
            d = math.hypot(m.x - self.x, m.y - self.y)
            if d > vision:
                continue
            score = d + 0.8 * m.perception.near_friends - 3.0 * (1.0 - m.growth)
            if score < best_score:
                best, best_score = m, score
        return best

    def _wander(self, sim: "Simulation") -> None:
        if sim.clock.is_night or self.energy_frac < HUNGRY_BELOW:
            self.state = PredatorState.WANDER
            if not self.path:
                rng = sim.rng
                for _ in range(6):
                    self.heading += rng.uniform(-1.0, 1.0)
                    r = rng.uniform(3.0, sim.config.predator_vision)
                    tx = self.x + math.cos(self.heading) * r
                    ty = self.y + math.sin(self.heading) * r
                    if sim.terrain.passable(tx, ty) and self.go_to(sim.terrain, (tx, ty)):
                        break
        else:
            self.state = PredatorState.REST  # well fed predators doze through the day
            self.path.clear()

    # ------------------------------------------------------------------ acting

    def act(self, sim: "Simulation") -> None:
        self._moved = 0.0
        if self.busy_ticks > 0:
            self.busy_ticks -= 1
            if self.state is PredatorState.RETREAT and self.path:
                self._walk(sim)
            if self.busy_ticks == 0:
                self.state = PredatorState.WANDER
            return

        if self.state is PredatorState.HUNT and self.prey is not None:
            prey = self.prey
            if not prey.alive:
                self.prey = None
                return
            if math.hypot(prey.x - self.x, prey.y - self.y) <= CATCH_RANGE:
                attack(sim, self, prey)
                return
            self.chase_ticks += 1
            if self.chase_ticks > CHASE_GIVE_UP_DAYS * sim.config.ticks_per_day:
                self.prey = None  # too quick or too well hidden: give up
                self.state = PredatorState.WANDER
                self.path.clear()
                return
            goal = self.target
            if goal is None or math.hypot(prey.x - goal[0], prey.y - goal[1]) > 1.0:
                self.go_to(sim.terrain, (prey.x, prey.y))

        if self.path:
            self._walk(sim)

    def _walk(self, sim: "Simulation") -> None:
        moved, _ = self.advance(sim.terrain, sim.config.predator_speed)
        self._moved += moved

    # ------------------------------------------------------------------ body

    def metabolise(self, sim: "Simulation") -> None:
        self.age += 1
        if self.breed_cooldown > 0:
            self.breed_cooldown -= 1
        drain = sim.config.predator_drain
        if self.state is PredatorState.REST:
            drain *= REST_DRAIN_FACTOR
        if sim.clock.season == 3:
            drain *= WINTER_DRAIN_FACTOR
        self.energy -= drain + self._moved * MOVE_DRAIN_PER_TILE
        if self.energy <= 0 or self.age >= self.max_age:
            self.alive = False


def defenders_of(sim: "Simulation", victim: Minion) -> list[tuple[Minion, float]]:
    """The victim and its allies close enough to help, with how much each contributes.

    Sleeping allies are woken by the commotion but only help half-heartedly.
    """
    defenders = [(victim, 1.0)]
    for m in sim.minion_index.query_radius(victim.x, victim.y, SOCIAL_RADIUS):
        if m is victim or not m.alive:
            continue
        if math.hypot(m.x - victim.x, m.y - victim.y) > SOCIAL_RADIUS:
            continue
        if m.is_ally(victim, sim):
            defenders.append((m, SLEEPING_HELPER_WEIGHT if m.action is Action.SLEEP else 1.0))
    return defenders


def attack(sim: "Simulation", predator: Predator, victim: Minion) -> bool:
    """The predator strikes. Returns True if the victim was killed, False if repelled."""
    cfg = sim.config
    tpd = cfg.ticks_per_day
    defenders = defenders_of(sim, victim)
    predator.prey = None
    predator.path.clear()

    if sum(fight_power(d) * w for d, w in defenders) >= cfg.predator_repel_power:
        # Driven off: the predator retreats, the defenders gain status and bond.
        predator.state = PredatorState.RETREAT
        predator.busy_ticks = int(RETREAT_DAYS * tpd)
        predator.energy -= RETREAT_COST
        predator.flee_from(sim.terrain, (victim.x, victim.y), cfg.predator_vision)
        victim.energy = max(1.0, victim.energy - VICTIM_SCARE_COST * victim.traits.max_energy)
        for i, (d, _) in enumerate(defenders):
            d.needs.status = min(1.0, d.needs.status + DEFENCE_STATUS)
            for other, _ in defenders[i + 1 :]:
                sim.relations.add(d.id, other.id, DEFENCE_BOND)
        sim.repelled += 1
        return False

    victim.die(DeathCause.PREDATOR)
    meal = cfg.predator_kill_energy * victim.growth  # juveniles are a smaller meal
    predator.energy = min(predator.max_energy, predator.energy + meal)
    predator.kills += 1
    predator.state = PredatorState.REST
    predator.busy_ticks = int(DIGEST_DAYS * tpd)
    sim.kills += 1
    return True
