import numpy as np

from lifesim.agents.brain import Action
from lifesim.agents.genome import GENE_NAMES, Genome
from lifesim.agents.minion import DeathCause
from lifesim.agents.predator import PredatorState, attack
from lifesim.config import SimConfig
from lifesim.core.simulation import Simulation
from lifesim.world.terrain import TerrainMap


def world(**overrides) -> Simulation:
    cfg = SimConfig(seed=21, map_width=40, map_height=40, initial_minions=0, initial_predators=0)
    for k, v in overrides.items():
        setattr(cfg, k, v)
    sim = Simulation(cfg)
    sim.terrain = TerrainMap(np.zeros((40, 40), dtype=np.uint8))
    sim.forest.trees.clear()
    sim.forest.index.clear()
    return sim


def adult(sim, x, y, **genes):
    m = sim.spawn_minion(x, y, Genome({n: 0.5 for n in GENE_NAMES} | genes))
    m.age = m.maturity
    m.energy = m.traits.max_energy
    return m


def midnight(sim):
    sim.clock.tick = sim.config.ticks_per_day * 2


def test_hungry_predator_hunts_and_kills_a_lone_minion():
    sim = world()
    midnight(sim)
    victim = adult(sim, 20, 20, speed=0.0, vision=0.0)
    victim.action = Action.SLEEP
    p = sim.spawn_predator(24, 20, energy_frac=0.3)
    energy_before = p.energy
    sim._rebuild_index()
    for _ in range(300):
        sim.step()
        if not victim.alive:
            break
    assert not victim.alive and victim.death_cause is DeathCause.PREDATOR
    assert sim.kills == 1 and p.kills == 1
    assert p.energy > energy_before
    assert sim.deaths[DeathCause.PREDATOR] == 1


def test_group_drives_a_predator_off():
    sim = world()
    victim = adult(sim, 20, 20, strength=0.5)
    friends = [adult(sim, 21 + i * 0.5, 21, strength=0.8) for i in range(2)]
    for f in friends:
        sim.relations.set(f.id, victim.id, 0.9)
    p = sim.spawn_predator(20.5, 20, energy_frac=0.3)
    sim._rebuild_index()
    killed = attack(sim, p, victim)
    assert not killed and victim.alive
    assert p.state is PredatorState.RETREAT and p.busy_ticks > 0
    assert sim.repelled == 1
    assert all(m.needs.status > 0 for m in [victim, *friends])
    assert sim.relations.get(friends[0].id, friends[1].id) > 0  # facing danger together bonds


def test_lone_minion_cannot_repel():
    sim = world()
    victim = adult(sim, 20, 20, strength=1.0)
    p = sim.spawn_predator(20.5, 20)
    sim._rebuild_index()
    assert attack(sim, p, victim)
    assert not victim.alive


def test_minion_flees_from_a_prowling_predator():
    sim = world()
    sim.clock.tick = sim.config.ticks_per_day // 2  # noon, good vision
    m = adult(sim, 20, 20, fearfulness=0.8)
    p = sim.spawn_predator(23, 20, energy_frac=0.3)
    p.state = PredatorState.HUNT
    sim._rebuild_index()
    m._redecide = True
    m.think(sim)
    assert m.perception.threat > 0.3
    assert m.action is Action.FLEE
    assert m.target is not None and m.target[0] < m.x  # running away from the predator


def test_well_fed_predator_breeds():
    sim = world(predator_breed_cooldown_days=1)
    sim.clock.tick = sim.config.ticks_per_day // 2
    p = sim.spawn_predator(20, 20, energy_frac=1.0)
    sim.step()
    assert len(sim.predators) == 2
    assert p.energy < 0.7 * p.max_energy  # breeding is costly
    assert p.breed_cooldown > 0


def test_sated_predator_rests_by_day_and_prowls_at_night():
    sim = world()
    sim.clock.tick = sim.config.ticks_per_day // 2
    p = sim.spawn_predator(20, 20, energy_frac=0.95)
    p.breed_cooldown = 10**6
    for _ in range(12):
        sim.step()
    assert p.state is PredatorState.REST
    sim.clock.tick = sim.config.ticks_per_day * 3
    for _ in range(12):
        sim.step()
    assert p.state is PredatorState.WANDER


def test_predators_starve_and_immigrate_in_spring():
    sim = world(predator_drain=5.0)
    sim.spawn_predator(20, 20)
    for _ in range(sim.config.ticks_per_day):
        sim.step()
    assert not [p for p in sim.predators if p.id == 0]
    # With nobody left, newcomers arrive on some spring/summer morning.
    days = 0
    while not sim.predators and days < 20:
        for _ in range(sim.config.ticks_per_day):
            sim.step()
        days += 1
    assert sim.predators


def test_predator_simulation_is_deterministic():
    def run():
        sim = Simulation(SimConfig(seed=8, map_width=50, map_height=40, initial_minions=40))
        for _ in range(3000):
            sim.step()
        return (
            [(m.id, round(m.x, 5), round(m.y, 5)) for m in sim.minions],
            [(p.id, round(p.x, 5), round(p.y, 5)) for p in sim.predators],
            sim.kills,
        )

    assert run() == run()
