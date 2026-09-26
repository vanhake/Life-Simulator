"""Social interactions between minions: bonding by proximity, fights and food sharing."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from lifesim.agents.brain import Action
from lifesim.agents.minion import FIGHT_RANGE, SOCIAL_RADIUS, DeathCause, Minion

if TYPE_CHECKING:
    from lifesim.core.simulation import Simulation

# Bonding
BOND_PER_DAY = 1.2  # relation gained per day spent close together (at average sociability)
OUTSIDER_BOND = 0.3  # members of different groups warm up to each other more slowly
RELATION_HALF_LIFE_DAYS = 3.0
KIN_BOND = 0.6  # initial relation between parent and child

# Fights
FIGHT_DAMAGE = 0.25  # fraction of the loser's max energy lost
FIGHT_EXERTION = 0.05  # fraction of the winner's max energy spent
LOOT_SHARE = 0.5  # part of the loser's loss the winner takes (stolen food)
FIGHT_ENMITY = 0.6
HELPER_ENMITY = 0.2
HELPER_WEIGHT = 0.5  # how much an ally's strength adds to a fighter's power
FIGHT_COOLDOWN_DAYS = 0.25
STATUS_PER_WIN = 0.1
STATUS_PER_LOSS = 0.05

# Sharing
SHARE_FRACTION = 0.2  # of the giver's max energy
SHARE_KEEP = 0.5  # the giver never drops below this fraction of its max energy
SHARE_BOND = 0.25
STATUS_PER_SHARE = 0.08


def bond_nearby(sim: "Simulation", days: float) -> None:
    """Minions that spend time close together grow fond of each other."""
    relations = sim.relations
    for m in sim.minions:
        if m.action is Action.SLEEP and m.group_id is None:
            continue
        for other in sim.minion_index.query_radius(m.x, m.y, SOCIAL_RADIUS):
            if other.id <= m.id or not other.alive:
                continue
            if math.hypot(other.x - m.x, other.y - m.y) > SOCIAL_RADIUS:
                continue
            if relations.get(m.id, other.id) < 0:
                continue  # enemies do not warm up just by being near each other
            sociability = (m.genome["sociability"] + other.genome["sociability"]) / 2
            gain = BOND_PER_DAY * days * (0.2 + 1.6 * sociability)
            if m.group_id is not None and other.group_id is not None and m.group_id != other.group_id:
                gain *= OUTSIDER_BOND
            relations.add(m.id, other.id, gain)
    relations.decay(0.5 ** (days / RELATION_HALF_LIFE_DAYS))


def fight_power(m: Minion) -> float:
    return (0.3 + m.genome["strength"]) * (0.5 + 0.5 * m.energy_frac) * m.growth


def _helpers(sim: "Simulation", fighter: Minion, opponent: Minion) -> list[Minion]:
    """Awake allies of `fighter` close enough to jump in."""
    return [
        h
        for h in sim.minion_index.query_radius(fighter.x, fighter.y, SOCIAL_RADIUS)
        if h is not fighter
        and h is not opponent
        and h.alive
        and h.action is not Action.SLEEP
        and math.hypot(h.x - fighter.x, h.y - fighter.y) <= SOCIAL_RADIUS
        and h.is_ally(fighter, sim)
        and not h.is_ally(opponent, sim)
    ]


def resolve_fights(sim: "Simulation") -> None:
    for attacker in list(sim.minions):
        defender = attacker.target_minion
        if attacker.action is not Action.FIGHT or defender is None:
            continue
        if not (attacker.alive and defender.alive) or attacker.fight_cooldown > 0:
            continue
        if math.hypot(defender.x - attacker.x, defender.y - attacker.y) > FIGHT_RANGE:
            continue
        fight(sim, attacker, defender)


def fight(sim: "Simulation", attacker: Minion, defender: Minion) -> Minion:
    """Resolve a fight and return the winner. Allies nearby lend their strength."""
    a_help = _helpers(sim, attacker, defender)
    d_help = _helpers(sim, defender, attacker)
    pa = fight_power(attacker) + HELPER_WEIGHT * sum(fight_power(h) for h in a_help)
    pd = fight_power(defender) + HELPER_WEIGHT * sum(fight_power(h) for h in d_help)
    attacker_wins = sim.rng.random() < pa / (pa + pd)
    winner, loser = (attacker, defender) if attacker_wins else (defender, attacker)
    winner_help = a_help if attacker_wins else d_help

    damage = FIGHT_DAMAGE * loser.traits.max_energy
    loot = min(damage, loser.energy) * LOOT_SHARE
    loser.energy -= damage
    winner.energy = min(
        winner.traits.max_energy,
        winner.energy - FIGHT_EXERTION * winner.traits.max_energy + loot,
    )

    winner.needs.status = min(1.0, winner.needs.status + STATUS_PER_WIN)
    loser.needs.status = max(0.0, loser.needs.status - STATUS_PER_LOSS)
    winner.fights_won += 1
    loser.fights_lost += 1
    sim.relations.add(attacker.id, defender.id, -FIGHT_ENMITY)
    for h in winner_help:
        sim.relations.add(h.id, loser.id, -HELPER_ENMITY)
        sim.relations.add(h.id, winner.id, HELPER_ENMITY)  # fighting side by side bonds

    cooldown = int(FIGHT_COOLDOWN_DAYS * sim.config.ticks_per_day)
    for m in (attacker, defender):
        m.fight_cooldown = cooldown
        m.target_minion = None
        m.path.clear()
        m._redecide = True
    winner.action = Action.REST

    if loser.energy <= 0:
        loser.energy = 0
        loser.die(DeathCause.FIGHT)
    else:
        loser.target_tree = None
        loser.action = Action.FLEE
        loser._flee(sim, (winner.x, winner.y))
        loser._redecide = False  # keep running for a moment before thinking again
    sim.fights += 1
    return winner


def share(sim: "Simulation", giver: Minion, receiver: Minion) -> float:
    """Give food energy to a hungry friend. Returns the amount given."""
    amount = min(
        SHARE_FRACTION * giver.traits.max_energy,
        receiver.traits.max_energy - receiver.energy,
        giver.energy - SHARE_KEEP * giver.traits.max_energy,
    )
    giver.target_minion = None
    giver.action = Action.REST
    giver._redecide = True
    if amount <= 1.0:
        return 0.0
    giver.energy -= amount
    receiver.energy += amount
    sim.relations.add(giver.id, receiver.id, SHARE_BOND)
    giver.needs.status = min(1.0, giver.needs.status + STATUS_PER_SHARE)
    giver.times_shared += 1
    sim.shares += 1
    return amount
