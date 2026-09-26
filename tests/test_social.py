import random

import numpy as np

from lifesim.agents.brain import Action, Perception, score_actions
from lifesim.agents.genome import GENE_NAMES, Genome
from lifesim.agents.minion import DeathCause
from lifesim.config import SimConfig
from lifesim.core.simulation import Simulation
from lifesim.social import interactions
from lifesim.social.groups import Groups
from lifesim.social.relations import Relations
from lifesim.world.terrain import TerrainMap


def world(**overrides) -> Simulation:
    cfg = SimConfig(seed=13, map_width=40, map_height=40, initial_minions=0, initial_predators=0)
    for k, v in overrides.items():
        setattr(cfg, k, v)
    sim = Simulation(cfg)
    sim.terrain = TerrainMap(np.zeros((40, 40), dtype=np.uint8))
    sim.forest.trees.clear()
    sim.forest.index.clear()
    sim.clock.tick = cfg.ticks_per_day // 2
    return sim


def genome(**genes: float) -> Genome:
    return Genome({n: 0.5 for n in GENE_NAMES} | genes)


def adult(sim, x, y, **genes):
    m = sim.spawn_minion(x, y, genome(**genes))
    m.age = m.maturity
    m.energy = m.traits.max_energy
    return m


# ---------------------------------------------------------------- relations


def test_relations_are_symmetric_clamped_and_forgotten():
    r = Relations()
    r.add(1, 2, 0.7)
    assert r.get(2, 1) == 0.7
    r.add(1, 2, 5)
    assert r.get(1, 2) == 1.0
    r.set(3, 4, 0.03)
    r.decay(0.5)
    assert r.get(3, 4) == 0.0 and r.get(1, 2) == 0.5
    r.remove(1)
    assert r.get(2, 1) == 0.0 and r.pairs() == 0


def test_time_together_builds_friendship_and_kin_start_close():
    sim = world()
    a, b = adult(sim, 10, 10, sociability=0.9), adult(sim, 11, 10, sociability=0.9)
    far = adult(sim, 35, 35)
    sim._rebuild_index()
    for _ in range(10):
        interactions.bond_nearby(sim, 0.05)
    assert sim.relations.get(a.id, b.id) > 0.3
    assert sim.relations.get(a.id, far.id) == 0.0
    child = sim.reproduce(a, b)
    assert sim.relations.get(a.id, child.id) == interactions.KIN_BOND


# ---------------------------------------------------------------- groups


def _clique(sim, members, value=0.8):
    for i, a in enumerate(members):
        for b in members[i + 1 :]:
            sim.relations.set(a.id, b.id, value)


def test_two_cliques_form_two_groups_with_leaders_and_stable_ids():
    sim = world()
    left = [adult(sim, 5 + i, 5) for i in range(4)]
    right = [adult(sim, 30 + i, 30) for i in range(5)]
    loner = adult(sim, 20, 20)
    _clique(sim, left)
    _clique(sim, right)
    sim.relations.set(left[0].id, right[0].id, 0.45)  # one weak bridge must not merge them
    left[2].needs.status = 0.9

    groups = Groups()
    groups.update(sim.minions, sim.relations, 0, random.Random(1))
    assert len(groups) == 2
    sizes = sorted(len(g.members) for g in groups.groups.values())
    assert sizes == [4, 5]
    assert loner.group_id is None
    left_group = groups.get(left[0].group_id)
    assert left_group.leader == left[2].id
    old_ids = {m.id: m.group_id for m in left + right}

    # A member leaves, a newcomer befriends the right group: ids survive.
    sim.relations.remove(left[3].id)
    newcomer = adult(sim, 31, 31)
    for m in right:
        sim.relations.set(newcomer.id, m.id, 0.8)
    groups.update(sim.minions, sim.relations, 1, random.Random(1))
    assert left[0].group_id == old_ids[left[0].id]
    assert right[0].group_id == old_ids[right[0].id] == newcomer.group_id


def test_dense_friendship_chain_does_not_become_one_giant_group():
    sim = world()
    # Two dense clusters joined by a single chain of moderate friendships.
    a = [adult(sim, 2 + i, 2) for i in range(6)]
    b = [adult(sim, 30 + i, 30) for i in range(6)]
    _clique(sim, a, 0.9)
    _clique(sim, b, 0.9)
    chain = [adult(sim, 10 + 3 * i, 10 + 3 * i) for i in range(4)]
    links = [a[0]] + chain + [b[0]]
    for x, y in zip(links, links[1:]):
        sim.relations.set(x.id, y.id, 0.45)
    groups = Groups()
    groups.update(sim.minions, sim.relations, 0, random.Random(3))
    assert a[1].group_id is not None and b[1].group_id is not None
    assert a[1].group_id != b[1].group_id


# ---------------------------------------------------------------- allies & perception


def test_allies_are_neither_threats_nor_rivals():
    sim = world()
    me = adult(sim, 10, 10, strength=0.1)
    brute = adult(sim, 11, 10, strength=1.0, aggression=1.0)
    sim._rebuild_index()
    p = me.perceive(sim)
    assert p.threat > 0 and p.rival is brute
    sim.relations.set(me.id, brute.id, 0.8)
    p = me.perceive(sim)
    assert p.threat == 0 and p.rival is None


def test_well_fed_altruist_notices_hungry_friend():
    sim = world()
    giver = adult(sim, 10, 10, altruism=1.0)
    friend = adult(sim, 12, 10)
    friend.energy = friend.traits.max_energy * 0.2
    sim.relations.set(giver.id, friend.id, 0.8)
    sim._rebuild_index()
    p = giver.perceive(sim)
    assert p.needy_friend is friend
    sim.rng.seed(0)
    s = score_actions(giver, sim, p)
    assert max(s, key=s.get) is Action.SHARE


def test_aggressive_strong_minion_picks_fights_over_food():
    sim = world()
    bully = adult(sim, 10, 10, strength=1.0, aggression=1.0)
    other = adult(sim, 11, 10, strength=0.2)
    bully.energy = bully.traits.max_energy * 0.4
    p = Perception(rival=other, rival_over_food=True)
    sim.rng.seed(0)
    s = score_actions(bully, sim, p)
    assert max(s, key=s.get) is Action.FIGHT
    meek = adult(sim, 12, 12, strength=0.2, aggression=0.0)
    s = score_actions(meek, sim, Perception(rival=bully))
    assert Action.FIGHT not in s


# ---------------------------------------------------------------- fights & sharing


def test_fight_outcome_and_consequences():
    sim = world()
    strong = adult(sim, 10, 10, strength=1.0)
    weak = adult(sim, 10.5, 10, strength=0.0)
    wins = 0
    for seed in range(40):
        sim.rng.seed(seed)
        strong.energy, weak.energy = strong.traits.max_energy, weak.traits.max_energy
        weak.alive = True
        if interactions.fight(sim, weak, strong) is strong:
            wins += 1
    assert wins >= 30  # power 1.3 vs 0.3 -> ~81 %

    sim.rng.seed(1)
    strong.energy = strong.traits.max_energy * 0.5
    weak.energy = weak.traits.max_energy
    status_before = strong.needs.status
    winner = interactions.fight(sim, weak, strong)
    loser = weak if winner is strong else strong
    assert winner.needs.status > status_before or winner is weak
    assert loser.energy < loser.traits.max_energy
    assert sim.relations.get(weak.id, strong.id) < 0
    assert loser.action is Action.FLEE and loser.fight_cooldown > 0


def test_allies_help_in_a_fight():
    def defender_wins(with_friends: bool) -> int:
        sim = world()
        attacker = adult(sim, 10, 10, strength=0.6)
        defender = adult(sim, 10.5, 10, strength=0.6)
        if with_friends:
            for i in range(3):
                f = adult(sim, 11 + i * 0.5, 11, strength=0.8)
                sim.relations.set(f.id, defender.id, 0.9)
        sim._rebuild_index()
        wins = 0
        for seed in range(100):
            sim.rng.seed(seed)
            attacker.energy = attacker.traits.max_energy
            defender.energy = defender.traits.max_energy
            if interactions.fight(sim, attacker, defender) is defender:
                wins += 1
        return wins

    alone, helped = defender_wins(False), defender_wins(True)
    assert 35 <= alone <= 65  # even match
    assert helped >= alone + 15  # expected ~74 % with three helpers


def test_losing_a_fight_can_kill():
    sim = world()
    a = adult(sim, 10, 10, strength=1.0)
    b = adult(sim, 10.5, 10, strength=0.0)
    b.energy = 1.0
    sim.rng.seed(0)
    while interactions.fight(sim, b, a) is not a:
        b.alive, b.energy = True, 1.0
    assert not b.alive and b.death_cause is DeathCause.FIGHT


def test_sharing_moves_energy_and_builds_bond():
    sim = world()
    giver = adult(sim, 10, 10)
    taker = adult(sim, 10.5, 10)
    taker.energy = 5.0
    before = giver.energy + taker.energy
    amount = sim.share(giver, taker)
    assert amount > 0
    assert abs(giver.energy + taker.energy - before) < 1e-9
    assert giver.energy >= 0.5 * giver.traits.max_energy
    assert sim.relations.get(giver.id, taker.id) > 0
    assert giver.needs.status > 0 and sim.shares == 1


def test_social_simulation_forms_groups_and_stays_consistent():
    sim = Simulation(SimConfig(seed=4, map_width=60, map_height=45, initial_minions=60, initial_predators=0))
    for _ in range(sim.config.ticks_per_day * 2):
        sim.step()
    assert len(sim.groups) >= 2
    alive = {m.id for m in sim.minions}
    for g in sim.groups.groups.values():
        assert g.members <= alive and g.leader in g.members
    for m in sim.minions:
        for other in sim.relations.of(m.id):
            assert other in alive  # the dead are forgotten
