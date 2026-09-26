import random

import numpy as np

from lifesim.agents.genome import GENE_NAMES, Genome
from lifesim.agents.minion import Action, DeathCause
from lifesim.config import SimConfig
from lifesim.core.clock import Clock
from lifesim.core.simulation import Simulation
from lifesim.world.terrain import Terrain, TerrainMap


def empty_world(**overrides) -> Simulation:
    """A small all-grass world without trees or minions."""
    cfg = SimConfig(seed=3, map_width=30, map_height=30, initial_minions=0, initial_predators=0)
    for k, v in overrides.items():
        setattr(cfg, k, v)
    sim = Simulation(cfg)
    sim.terrain = TerrainMap(np.zeros((30, 30), dtype=np.uint8))
    sim.forest.trees.clear()
    sim.forest.index.clear()
    sim.clock.tick = cfg.ticks_per_day // 2  # noon: nobody wants to sleep
    return sim


def adult(sim: Simulation, x: float, y: float, seed: int = 0):
    """A mature, well-fed minion that longs for a partner."""
    m = sim.spawn_minion(x, y, Genome.random(random.Random(seed)))
    m.age = m.maturity
    m.energy = m.traits.max_energy
    m.needs.partner = 0.0
    return m


def test_clock_day_night_and_seasons():
    c = Clock(ticks_per_day=100, days_per_season=2)
    assert c.is_night and c.daylight == 0.0  # midnight
    c.tick = 50
    assert not c.is_night and c.daylight == 1.0  # noon
    assert c.clock_text() == "12:00"
    c.tick = 100 * 2 * 3  # day 6 -> 4th season
    assert c.season == 3 and c.season_name == "Winter"
    c.tick = 100 * 2 * 4
    assert c.season == 0 and c.year == 1


def test_two_ready_adults_produce_a_child():
    sim = empty_world()
    a, b = adult(sim, 10, 10, 1), adult(sim, 10.5, 10, 2)
    sim._rebuild_index()
    energy_before = a.energy + b.energy
    sim.step()
    assert sim.births == 1
    child = sim.minions[-1]
    assert child.parents == (a.id, b.id)
    assert child.generation == 1
    assert not child.is_adult
    assert a.mate_cooldown > 0 and b.mate_cooldown > 0
    # Energy is transferred, not created (up to per-tick drain and the child's cap).
    assert child.energy <= energy_before - (a.energy + b.energy) + 1e-6
    assert sim.lineage[a.id].children == [child.id]
    for g in GENE_NAMES:
        assert 0.0 <= child.genome[g] <= 1.0


def test_hungry_or_young_minions_do_not_mate():
    sim = empty_world()
    a, b = adult(sim, 10, 10, 1), adult(sim, 10.5, 10, 2)
    a.energy = a.traits.max_energy * 0.5
    c, d = adult(sim, 20, 20, 3), adult(sim, 20.5, 20, 4)
    d.age = 0
    sim._rebuild_index()
    for _ in range(20):
        sim.step()
    assert sim.births == 0


def test_close_kin_do_not_mate():
    sim = empty_world()
    a, b = adult(sim, 10, 10, 1), adult(sim, 10.5, 10, 2)
    child = sim.reproduce(a, b)
    sibling = sim.reproduce(a, b)
    assert child.is_close_kin(a) and a.is_close_kin(child)
    assert child.is_close_kin(sibling)
    stranger = adult(sim, 3, 3, 9)
    assert not child.is_close_kin(stranger)


def test_mutation_introduces_variation():
    sim = empty_world(mutation_rate=1.0, mutation_strength=0.2)
    a, b = adult(sim, 10, 10, 1), adult(sim, 10.5, 10, 2)
    child = sim.reproduce(a, b)
    assert any(child.genome[g] not in (a.genome[g], b.genome[g]) for g in GENE_NAMES)


def test_minion_dies_of_old_age():
    sim = empty_world()
    m = adult(sim, 10, 10)
    m.age = m.max_age - 1
    sim.step()
    assert not m.alive and m.death_cause is DeathCause.OLD_AGE
    assert sim.lineage[m.id].cause == DeathCause.OLD_AGE.value


def test_population_cap_is_respected():
    sim = empty_world(max_population=2)
    adult(sim, 10, 10, 1), adult(sim, 10.5, 10, 2)
    sim._rebuild_index()
    for _ in range(10):
        sim.step()
    assert len(sim.minions) == 2
    assert all(m.action is not Action.SEEK_MATE for m in sim.minions)


def test_night_reduces_vision():
    sim = empty_world(night_vision_factor=0.5)
    m = adult(sim, 10, 10)
    sim.clock.tick = sim.config.ticks_per_day - 1  # step() moves to midnight
    sim.step()
    assert abs(m.vision(sim) - m.traits.vision * 0.5) < 1e-9


def test_trees_age_die_and_reseed_within_capacity():
    cfg = SimConfig(seed=5, map_width=40, map_height=30, initial_minions=0, initial_predators=0)
    sim = Simulation(cfg)
    forest = sim.forest
    for _ in range(cfg.ticks_per_day * 30):
        forest.update(sim.clock, cfg, sim.terrain, sim.rng)
        sim.clock.tick += 1
    assert forest.died > 0 and forest.born > 0
    for kind in Terrain:
        count = sum(1 for t in forest.trees if t.terrain is kind)
        assert count <= forest.capacity[kind] + 1
    tiles = [t.tile for t in forest.trees]
    assert len(tiles) == len(set(tiles))  # at most one tree per tile
    assert all(sim.terrain.passable(t.x, t.y) for t in forest.trees)


def test_saplings_bear_fruit_only_when_mature():
    cfg = SimConfig(seed=5, map_width=20, map_height=20, initial_minions=0, initial_predators=0, tree_maturity_days=1)
    sim = Simulation(cfg)
    forest = sim.forest
    tile = next(
        (x, y) for y in range(20) for x in range(20)
        if sim.terrain.passable(x, y) and (x, y) not in forest._occupied
    )
    tree = forest.add(*tile, sim.terrain.at(*tile), has_fruit=False, maturity=cfg.ticks_per_day)
    for _ in range(cfg.ticks_per_day - 1):
        forest.update(sim.clock, cfg, sim.terrain, sim.rng)
    assert tree.is_sapling and not tree.has_fruit
    forest.update(sim.clock, cfg, sim.terrain, sim.rng)
    assert not tree.is_sapling and tree.has_fruit


def test_winter_slows_fruit_regrowth():
    cfg = SimConfig(seed=5, map_width=20, map_height=20, initial_minions=0, initial_predators=0, fruit_regrow_ticks=100)
    results = {}
    for season in (1, 3):  # summer, winter
        sim = Simulation(cfg)
        sim.clock.tick = season * cfg.days_per_season * cfg.ticks_per_day
        tree = next(t for t in sim.forest.trees if not t.is_sapling)
        tree.has_fruit = True
        sim.forest.eat(tree, cfg.fruit_regrow_ticks)
        n = 0
        while not tree.has_fruit:
            sim.forest.update(sim.clock, cfg, sim.terrain, sim.rng)
            n += 1
        results[season] = n
    assert results[3] > 3 * results[1]
