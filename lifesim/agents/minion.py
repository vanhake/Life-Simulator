"""Minion: body, needs, perception and execution of the action chosen by the brain."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from lifesim.agents.brain import Action, Perception, choose_action
from lifesim.agents.genome import Genome
from lifesim.agents.needs import Needs, clamp01
from lifesim.agents.movement import Mover

if TYPE_CHECKING:
    from lifesim.core.simulation import Simulation
    from lifesim.world.trees import Tree

__all__ = ["Action", "DeathCause", "Minion", "Traits"]


class DeathCause(Enum):
    STARVATION = "Verhungert"
    OLD_AGE = "Altersschwäche"
    FIGHT = "Im Kampf gestorben"
    PREDATOR = "Gefressen"


def lerp(lo: float, hi: float, t: float) -> float:
    return lo + (hi - lo) * t


# Energy the body burns per tick just by existing, and per tile travelled.
BASE_DRAIN = 0.02
MOVE_DRAIN_PER_TILE = 0.25
SLEEP_DRAIN_FACTOR = 0.6
REST_DRAIN_FACTOR = 0.85
EAT_RANGE = 0.6
MATE_RANGE = 1.0
SOCIAL_RADIUS = 4.0
THINK_INTERVAL = 6  # ticks between regular decisions
NEEDS_INTERVAL = 6  # ticks between need updates (applied with the accumulated time)
REGION_SIZE = 6  # tiles per exploration memory cell
AGGRESSION_THREAT_MIN = 0.6
STATUS_PER_CHILD = 0.15
FIGHT_RANGE = 1.0
RIVAL_RADIUS = 3.0  # strangers closer than this can be challenged
SHARE_RANGE = 1.2
SHARE_ABOVE = 0.75  # only minions this well fed give food away ...
NEEDY_BELOW = 0.4  # ... to friends this hungry
PREDATOR_THREAT = 1.3  # how frightening a hunting predator is at point-blank range


# Actions that approach another minion, and how close they need to get.
APPROACH_RANGE = {
    Action.SEEK_MATE: MATE_RANGE,
    Action.SOCIALIZE: 1.5,
    Action.FIGHT: FIGHT_RANGE,
    Action.SHARE: SHARE_RANGE,
}


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
    restlessness: float  # activity satisfaction lost per day when not moving
    loneliness: float  # belonging lost per day when alone
    boredom: float  # fulfilment lost per day

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
            restlessness=lerp(1.5, 8.0, g["activity_need"]),
            loneliness=lerp(0.2, 1.5, g["sociability"]),
            boredom=lerp(0.2, 1.2, g["curiosity"]),
        )


@dataclass(eq=False)
class Minion(Mover):
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
    needs: Needs = field(default_factory=Needs)
    alive: bool = True
    death_cause: DeathCause | None = None
    action: Action = Action.WANDER
    perception: Perception = field(default_factory=Perception)
    target_tree: "Tree | None" = None
    target_minion: "Minion | None" = None  # partner or company being approached
    path: list[tuple[float, float]] = field(default_factory=list)
    mate_cooldown: int = 0
    heading: float = 0.0
    fruits_eaten: int = 0
    children: int = 0
    group_id: int | None = None
    fight_cooldown: int = 0
    fights_won: int = 0
    fights_lost: int = 0
    times_shared: int = 0
    explored: dict[tuple[int, int], int] = field(default_factory=dict)  # region -> last tick
    _region: tuple[int, int] | None = None
    _moved: float = 0.0  # distance walked this tick
    _walked: float = 0.0  # distance walked since the last need update
    _slept: int = 0  # ticks slept since the last need update
    _redecide: bool = True

    def __post_init__(self) -> None:
        self.traits = Traits.from_genome(self.genome)
        self.energy = self.traits.max_energy * 0.8
        self.needs.hunger = self.energy_frac

    # ------------------------------------------------------------------ properties

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

    @property
    def skill(self) -> float:
        """Foraging skill in [0, 1) that grows with experience."""
        return 1.0 - math.exp(-self.fruits_eaten / 25)

    def vision(self, sim: "Simulation") -> float:
        return self.traits.vision * sim.vision_factor

    def can_mate(self, sim: "Simulation") -> bool:
        return (
            self.alive
            and self.is_adult
            and self.mate_cooldown <= 0
            and self.energy_frac >= sim.config.mate_energy_threshold
            and self.action is not Action.SLEEP
        )

    def is_close_kin(self, other: "Minion") -> bool:
        """Parents, children and siblings (incl. half-siblings) do not mate."""
        if self.parents and other.id in self.parents:
            return True
        if other.parents and self.id in other.parents:
            return True
        return bool(self.parents and other.parents and set(self.parents) & set(other.parents))

    def is_ally(self, other: "Minion", sim: "Simulation") -> bool:
        """Kin, friends and members of the same group stick together."""
        if self.group_id is not None and self.group_id == other.group_id:
            return True
        return sim.relations.is_friend(self.id, other.id) or self.is_close_kin(other)

    # ------------------------------------------------------------------ perception

    def perceive(self, sim: "Simulation") -> Perception:
        vision = self.vision(sim)
        p = Perception()
        if self.energy_frac < 0.97:
            p.fruit = self._find_fruit(sim, vision * (1 + 0.3 * self.skill))
        want_mate = self.can_mate(sim) and len(sim.minions) < sim.config.max_population
        may_fight = self.is_adult and self.fight_cooldown <= 0
        may_share = self.energy_frac > SHARE_ABOVE and self.genome["altruism"] > 0.2
        group = sim.groups.get(self.group_id)
        leader_id = group.leader if group is not None and group.leader != self.id else None
        mate_d = rival_d = needy_d = vision
        ally_d = other_d = leader = None
        nearest_ally = nearest_any = None
        my_strength = self.genome["strength"]

        for other in sim.minion_index.query_radius(self.x, self.y, vision):
            if other is self or not other.alive:
                continue
            d = math.hypot(other.x - self.x, other.y - self.y)
            if d > vision:
                continue
            ally = self.is_ally(other, sim)
            if d <= SOCIAL_RADIUS:
                p.near_count += 1
                if ally:
                    p.near_friends += 1
            if other.id == leader_id:
                leader = other
            if ally and (ally_d is None or d < ally_d):
                nearest_ally, ally_d = other, d
            if other_d is None or d < other_d:
                nearest_any, other_d = other, d
            if want_mate and d <= mate_d and other.can_mate(sim) and not self.is_close_kin(other):
                p.mate, mate_d = other, d
            if ally:
                if may_share and d <= needy_d and other.energy_frac < NEEDY_BELOW:
                    p.needy_friend, needy_d = other, d
                continue  # allies are neither rivals nor threats
            if may_fight and d <= RIVAL_RADIUS and d <= rival_d and other.is_adult:
                p.rival, rival_d = other, d
            aggression = other.genome["aggression"]
            if aggression > AGGRESSION_THREAT_MIN:
                edge = other.genome["strength"] - my_strength + 0.2
                if edge > 0:
                    t = (1 - d / vision) * (aggression - AGGRESSION_THREAT_MIN) * 2.5 * edge
                    if t > p.threat:
                        p.threat, p.threat_pos = t, (other.x, other.y)

        for predator in sim.predator_index.query_radius(self.x, self.y, vision):
            d = math.hypot(predator.x - self.x, predator.y - self.y)
            if d > vision or not predator.alive:
                continue
            t = (1 - d / vision) * PREDATOR_THREAT * (1.0 if predator.is_dangerous else 0.4)
            if t > p.threat:
                p.threat, p.threat_pos = t, (predator.x, predator.y)

        # Company protects: nearby minions, and friends even more, soften threats.
        shelter = 0.1 * min(p.near_count, 4) + 0.1 * min(p.near_friends, 3)
        p.threat = clamp01(p.threat * max(0.0, 1 - shelter))

        # Prefer the group leader as company, then friends, then anyone.
        company = leader or nearest_ally or nearest_any
        if company is not None:
            p.nearest_other = company
            p.nearest_other_dist = math.hypot(company.x - self.x, company.y - self.y)
        if p.rival is not None and p.fruit is not None:
            p.rival_over_food = p.rival.target_tree is p.fruit
        return p

    def _find_fruit(self, sim: "Simulation", radius: float) -> "Tree | None":
        best, best_d = None, radius
        for tree in sim.forest.index.query_radius(self.x, self.y, radius):
            if not tree.has_fruit:
                continue
            d = math.hypot(tree.x - self.x, tree.y - self.y)
            if d <= best_d:
                best, best_d = tree, d
        return best

    # ------------------------------------------------------------------ decision

    def think(self, sim: "Simulation") -> None:
        if not self._redecide and (sim.tick + self.id) % THINK_INTERVAL:
            return
        self._redecide = False
        p = self.perceive(sim)
        self.perception = p
        self.needs.safety = 1.0 - p.threat
        previous = self.action
        action = choose_action(self, sim, p)
        self.action = action

        if action is Action.SEEK_FOOD:
            if p.fruit is not None:
                if p.fruit is not self.target_tree or not self.path:
                    self.target_tree = p.fruit
                    self._go_to(sim, (p.fruit.x, p.fruit.y))
            elif previous is not Action.SEEK_FOOD or not self.path:
                self.target_tree = None
                self._go_to_unexplored(sim)
        elif action in (Action.SLEEP, Action.REST):
            self.path.clear()
        elif action is Action.FLEE:
            self._flee(sim, p.threat_pos)
        elif action is Action.WANDER:
            if previous is not Action.WANDER or not self.path:
                self._go_random(sim)
        elif action is Action.SOCIALIZE:
            self.target_minion = p.nearest_other
            if p.nearest_other_dist > 1.5:
                self._go_to(sim, (p.nearest_other.x, p.nearest_other.y))
            else:
                self.path.clear()
        elif action is Action.SEEK_MATE:
            self.target_minion = p.mate
            self._go_to(sim, (p.mate.x, p.mate.y))
        elif action is Action.EXPLORE:
            if previous is not Action.EXPLORE or not self.path:
                self._go_to_unexplored(sim)
        elif action is Action.FIGHT:
            self.target_minion = p.rival
            self._go_to(sim, (p.rival.x, p.rival.y))
        elif action is Action.SHARE:
            self.target_minion = p.needy_friend
            self._go_to(sim, (p.needy_friend.x, p.needy_friend.y))

        if action is not Action.SEEK_FOOD:
            self.target_tree = None
        if action not in APPROACH_RANGE:
            self.target_minion = None

    # ------------------------------------------------------------------ destinations

    def _go_to(self, sim: "Simulation", goal: tuple[float, float]) -> bool:
        return self.go_to(sim.terrain, goal)

    def _go_random(self, sim: "Simulation") -> None:
        # Keep roughly the current heading so wandering looks purposeful rather than jittery.
        rng, vision = sim.rng, self.vision(sim)
        for _ in range(8):
            self.heading += rng.uniform(-1.2, 1.2)
            r = rng.uniform(2.0, max(2.0, vision))
            tx, ty = self.x + math.cos(self.heading) * r, self.y + math.sin(self.heading) * r
            if sim.terrain.passable(tx, ty) and self._go_to(sim, (tx, ty)):
                return
        self.path = []

    def _go_to_unexplored(self, sim: "Simulation") -> None:
        """Head for the least recently visited region among a few random candidates."""
        rng, vision = sim.rng, self.vision(sim)
        best, best_last = None, math.inf
        for _ in range(6):
            angle = rng.uniform(0, 2 * math.pi)
            r = rng.uniform(vision, 2 * vision)
            tx, ty = self.x + math.cos(angle) * r, self.y + math.sin(angle) * r
            if not sim.terrain.passable(tx, ty):
                continue
            last = self.explored.get((int(tx) // REGION_SIZE, int(ty) // REGION_SIZE), -1)
            if last < best_last:
                best, best_last = (tx, ty), last
        if best is None or not self._go_to(sim, best):
            self._go_random(sim)

    def _flee(self, sim: "Simulation", threat: tuple[float, float] | None) -> None:
        if threat is not None:
            self.flee_from(sim.terrain, threat, max(3.0, self.vision(sim) * 0.6))

    # ------------------------------------------------------------------ acting

    def act(self, sim: "Simulation") -> None:
        self._moved = 0.0
        action = self.action

        if action is Action.SEEK_FOOD and self.target_tree is not None:
            tree = self.target_tree
            if not tree.has_fruit:
                self._redecide = True
                self.path.clear()
                return
            if math.hypot(tree.x - self.x, tree.y - self.y) <= EAT_RANGE:
                self._eat(sim, tree)
                return

        if action in APPROACH_RANGE:
            other = self.target_minion
            if other is None or not other.alive:
                self._redecide = True
                self.path.clear()
                return
            d = math.hypot(other.x - self.x, other.y - self.y)
            if d <= APPROACH_RANGE[action]:
                self.path.clear()
                if action is Action.SHARE:
                    sim.share(self, other)
                # Mating and fights are resolved by the simulation; company is enjoyed.
                return
            # Re-aim if the other has wandered away from where we are heading.
            goal = self.target
            if goal is None or math.hypot(other.x - goal[0], other.y - goal[1]) > 1.5:
                self._go_to(sim, (other.x, other.y))

        if self.path:
            self._follow_path(sim)
            if not self.path and action not in (Action.SEEK_MATE, Action.SOCIALIZE):
                self._redecide = True

    def _eat(self, sim: "Simulation", tree: "Tree") -> None:
        if sim.forest.eat(tree, sim.config.fruit_regrow_ticks):
            self.energy = min(
                self.traits.max_energy,
                self.energy + sim.config.fruit_energy * self.traits.digestion,
            )
            self.fruits_eaten += 1
            self.action = Action.EAT
        self.target_tree = None
        self.path.clear()
        self._redecide = True

    def _follow_path(self, sim: "Simulation") -> None:
        moved, blocked = self.advance(sim.terrain, self.traits.speed)
        if blocked:
            self._redecide = True
        self._moved += moved
        self.energy -= moved * self.traits.move_drain

    # ------------------------------------------------------------------ body & needs

    def metabolise(self, sim: "Simulation") -> None:
        self.age += 1
        if self.mate_cooldown > 0:
            self.mate_cooldown -= 1
        if self.fight_cooldown > 0:
            self.fight_cooldown -= 1

        drain = self.traits.idle_drain
        if self.action is Action.SLEEP:
            drain *= SLEEP_DRAIN_FACTOR
            self._slept += 1
        elif self._moved == 0.0:
            drain *= REST_DRAIN_FACTOR
        self.energy -= drain
        self._walked += self._moved

        if (sim.tick + self.id) % NEEDS_INTERVAL == 0:
            self._update_needs(sim, NEEDS_INTERVAL)

        if self.energy <= 0:
            self.energy = 0
            self.die(DeathCause.STARVATION)
        elif self.age >= self.max_age:
            self.die(DeathCause.OLD_AGE)

    def _update_needs(self, sim: "Simulation", ticks: int) -> None:
        """Advance all needs by `ticks` ticks using what happened since the last update."""
        n, t = self.needs, self.traits
        days = ticks / sim.config.ticks_per_day
        slept_days = self._slept / sim.config.ticks_per_day
        awake_days = days - slept_days
        walked, self._walked, self._slept = self._walked, 0.0, 0

        n.hunger = clamp01(self.energy_frac)

        # Awake for a whole day drains rest completely; ~6 h of sleep restores it.
        n.rest = clamp01(n.rest + 4.0 * slept_days - 1.0 * awake_days)

        # Walking satisfies the urge to move, standing around (awake) builds it up.
        walk_days = walked / t.speed / sim.config.ticks_per_day
        idle_days = max(0.0, awake_days - walk_days)
        n.activity = clamp01(n.activity + 10.0 * walk_days - t.restlessness * idle_days)

        # Company satisfies belonging; friends count double.
        company = self.perception.near_count + self.perception.near_friends
        if company > 0:
            n.belonging = min(1.0, n.belonging + 2.0 * days * min(3, company))
        else:
            n.belonging = max(0.0, n.belonging - t.loneliness * days)

        if self.can_mate(sim):
            n.partner = max(0.0, n.partner - 2.0 * days)
        else:
            n.partner = min(1.0, n.partner + 2.0 * days)

        n.status = max(0.0, n.status - 0.1 * days)

        n.fulfilment = max(0.0, n.fulfilment - t.boredom * days)
        region = (int(self.x) // REGION_SIZE, int(self.y) // REGION_SIZE)
        if region != self._region:
            self._region = region
            last = self.explored.get(region)
            staleness = 1.0 if last is None else min(1.0, (sim.tick - last) / sim.config.ticks_per_day / 2)
            n.fulfilment = min(1.0, n.fulfilment + 0.25 * staleness)
            self.explored[region] = sim.tick

    def on_child_born(self) -> None:
        self.children += 1
        self.needs.status = min(1.0, self.needs.status + STATUS_PER_CHILD)
        self.needs.partner = 1.0

    def die(self, cause: DeathCause) -> None:
        self.alive = False
        self.death_cause = cause
        self.target_minion = None
        self.target_tree = None
