"""Utility AI: scores every possible action from needs and personality, picks the best.

Each score is roughly "how unsatisfied is the need" × "how much does this minion care
(gene)" × "is the level below satisfied enough (Maslow gate)". A bonus for the current
action prevents flickering between near-equal options.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from lifesim.agents.needs import clamp01, smoothstep

if TYPE_CHECKING:
    from lifesim.agents.minion import Minion
    from lifesim.core.simulation import Simulation
    from lifesim.world.trees import Tree


class Action(Enum):
    REST = "Ausruhen"
    WANDER = "Umherstreifen"
    SEEK_FOOD = "Futter suchen"
    EAT = "Essen"
    SLEEP = "Schlafen"
    FLEE = "Fliehen"
    SOCIALIZE = "Gesellschaft suchen"
    SEEK_MATE = "Partner suchen"
    EXPLORE = "Erkunden"


REST_BASELINE = 0.1
COMMITMENT_BONUS = 0.12
NOISE = 0.04


@dataclass
class Perception:
    fruit: "Tree | None" = None
    mate: "Minion | None" = None
    nearest_other: "Minion | None" = None
    nearest_other_dist: float = float("inf")
    near_count: int = 0  # minions within social radius
    threat: float = 0.0  # 0..1
    threat_pos: tuple[float, float] | None = None
    scores: dict[Action, float] = field(default_factory=dict)


def lerp(lo: float, hi: float, t: float) -> float:
    return lo + (hi - lo) * t


def score_actions(m: "Minion", sim: "Simulation", p: Perception) -> dict[Action, float]:
    n, g = m.needs, m.genome
    cfg = sim.config
    s: dict[Action, float] = {Action.REST: REST_BASELINE}

    # Level 1: hunger. 0.5 at the configured hunger threshold, 1.0 when starving.
    hunger = clamp01(0.5 * (1 - m.energy_frac) / max(1e-6, 1 - cfg.hunger_threshold))
    s[Action.SEEK_FOOD] = hunger if p.fruit is not None else hunger * 0.85

    # Level 1: sleep. At night minions sleep readily and keep sleeping while tired;
    # during the day only real exhaustion sends them to sleep.
    if sim.clock.is_night:
        sleep = 0.3 + (1 - n.rest) * 1.3
        if m.action is Action.SLEEP and n.rest < 0.98:
            sleep += 0.4
    else:
        sleep = smoothstep(0.3, 0.0, n.rest) * 1.2
    s[Action.SLEEP] = sleep

    # Level 1: need to move.
    s[Action.WANDER] = (1 - n.activity) * lerp(0.3, 1.0, g["activity_need"])

    # Level 2: safety – running away from threats trumps almost everything.
    if p.threat > 0 and p.threat_pos is not None:
        s[Action.FLEE] = p.threat * lerp(0.6, 1.4, g["fearfulness"]) * 1.5

    # Level 3: belonging and partnership.
    gate3 = n.gate(3)
    if p.nearest_other is not None:
        s[Action.SOCIALIZE] = (1 - n.belonging) * lerp(0.2, 1.0, g["sociability"]) * gate3
    if p.mate is not None:
        s[Action.SEEK_MATE] = (1 - n.partner) * lerp(0.6, 1.0, g["fertility"]) * gate3 + 0.1

    # Level 5: self-actualisation.
    s[Action.EXPLORE] = (1 - n.fulfilment) * lerp(0.1, 0.9, g["curiosity"]) * n.gate(5)

    rng = sim.rng
    for a in s:
        s[a] += rng.random() * NOISE
    if m.action in s:
        s[m.action] += COMMITMENT_BONUS
    return s


def choose_action(m: "Minion", sim: "Simulation", p: Perception) -> Action:
    p.scores = score_actions(m, sim, p)
    return max(p.scores, key=p.scores.__getitem__)
