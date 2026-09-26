import random

import numpy as np

from lifesim.agents.genome import GENE_NAMES, Genome
from lifesim.agents.minion import DeathCause, Minion
from lifesim.config import SimConfig
from lifesim.core.simulation import TREE_INTERVAL, Simulation
from lifesim.ui.camera import Camera
from lifesim.world.terrain import Terrain, TerrainMap, generate_terrain


def small_config(**overrides) -> SimConfig:
    cfg = SimConfig(seed=7, map_width=40, map_height=30, initial_minions=15, initial_predators=0)
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def snapshot(sim: Simulation) -> list[tuple]:
    return [(m.id, round(m.x, 6), round(m.y, 6), round(m.energy, 6)) for m in sim.minions]


def test_same_seed_is_deterministic():
    a, b = Simulation(small_config()), Simulation(small_config())
    for _ in range(500):
        a.step()
        b.step()
    assert snapshot(a) == snapshot(b)
    assert np.array_equal(a.terrain.tiles, b.terrain.tiles)


def test_different_seed_differs():
    a, b = Simulation(small_config(seed=1)), Simulation(small_config(seed=2))
    assert not np.array_equal(a.terrain.tiles, b.terrain.tiles)


def test_terrain_has_passable_majority():
    t = generate_terrain(80, 60, np.random.default_rng(3))
    assert t.tiles.shape == (60, 80)
    assert (t.tiles != Terrain.ROCK).mean() > 0.8


def test_genome_mutation_stays_in_range():
    rng = random.Random(0)
    g = Genome.random(rng)
    for _ in range(200):
        g = g.mutated(rng, rate=1.0, strength=0.5)
    assert set(g.genes) == set(GENE_NAMES)
    assert all(0.0 <= v <= 1.0 for v in g.genes.values())


def test_crossover_takes_genes_from_parents():
    rng = random.Random(0)
    a, b = Genome.random(rng), Genome.random(rng)
    child = Genome.crossover(a, b, rng)
    assert all(child[n] in (a[n], b[n]) for n in GENE_NAMES)


def test_minions_never_enter_rock():
    sim = Simulation(small_config(initial_minions=30))
    for _ in range(1500):
        sim.step()
        for m in sim.minions:
            assert sim.terrain.passable(m.x, m.y)


def test_hungry_minion_eats_nearby_fruit():
    sim = Simulation(small_config(initial_minions=0))
    tree = sim.forest.trees[0]
    tree.has_fruit = True
    m = sim.spawn_minion(tree.x + 0.3, tree.y, Genome.random(random.Random(1)))
    m.energy = m.traits.max_energy * 0.2
    before = m.energy
    sim.step()
    assert m.fruits_eaten == 1
    assert m.energy > before
    assert not tree.has_fruit


def test_fruit_regrows():
    sim = Simulation(small_config(initial_minions=0, fruit_regrow_ticks=5))
    tree = sim.forest.trees[0]
    tree.has_fruit = True
    sim.forest.eat(tree, sim.config.fruit_regrow_ticks)
    for _ in range(TREE_INTERVAL):  # trees are updated in batches
        sim.step()
    assert tree.has_fruit


def test_minion_starves_without_food():
    tiles = np.zeros((20, 20), dtype=np.uint8)
    sim = Simulation(small_config(initial_minions=0))
    sim.terrain = TerrainMap(tiles)
    sim.forest.trees.clear()
    sim.forest.index.clear()
    m = sim.spawn_minion(10, 10, Genome.random(random.Random(2)))
    m.energy = 1.0
    for _ in range(200):
        sim.step()
    assert not m.alive
    assert m.death_cause is DeathCause.STARVATION
    assert sim.minions == []
    assert sim.deaths[DeathCause.STARVATION] == 1


def test_faster_minions_burn_more_per_tile():
    slow = Minion(0, 0, 0, Genome({n: 0.5 for n in GENE_NAMES} | {"speed": 0.1}))
    fast = Minion(1, 0, 0, Genome({n: 0.5 for n in GENE_NAMES} | {"speed": 0.9}))
    assert fast.traits.speed > slow.traits.speed
    assert fast.traits.move_drain > slow.traits.move_drain


def test_camera_roundtrip_and_clamp():
    cam = Camera(800, 600, 100, 50)
    wx, wy = cam.screen_to_world(123, 45)
    assert cam.world_to_screen(wx, wy) == (123, 45)
    cam.zoom_at(4, 400, 300)
    cam.pan(-10_000, -10_000)
    assert (cam.x, cam.y) == (0.0, 0.0)
    cam.pan(10_000, 10_000)
    x, y, w, h = cam.visible_rect()
    assert abs(x + w - 100) < 1e-9 and abs(y + h - 50) < 1e-9
