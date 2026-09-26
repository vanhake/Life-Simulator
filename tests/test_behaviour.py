import random

import numpy as np

from lifesim.agents.brain import Action, Perception, score_actions
from lifesim.agents.genome import GENE_NAMES, Genome
from lifesim.agents.needs import Needs
from lifesim.config import SimConfig
from lifesim.core.simulation import Simulation
from lifesim.world.pathfinding import find_path, line_clear
from lifesim.world.terrain import Terrain, TerrainMap

G, R = Terrain.GRASS, Terrain.ROCK


def wall_map() -> TerrainMap:
    """20x20 grass with a vertical rock wall at x=10 that has a gap at y=17."""
    tiles = np.full((20, 20), G, dtype=np.uint8)
    tiles[:, 10] = R
    tiles[17, 10] = G
    return TerrainMap(tiles)


def world(tiles: TerrainMap | None = None, **overrides) -> Simulation:
    cfg = SimConfig(seed=11, map_width=20, map_height=20, initial_minions=0, initial_predators=0)
    for k, v in overrides.items():
        setattr(cfg, k, v)
    sim = Simulation(cfg)
    sim.terrain = tiles or TerrainMap(np.zeros((20, 20), dtype=np.uint8))
    sim.forest.trees.clear()
    sim.forest.index.clear()
    sim.forest._occupied.clear()
    sim.clock.tick = cfg.ticks_per_day // 2  # noon
    return sim


def neutral_genome(**genes: float) -> Genome:
    return Genome({n: 0.5 for n in GENE_NAMES} | genes)


# ---------------------------------------------------------------- path finding


def test_line_clear_detects_walls():
    t = wall_map()
    assert line_clear(t, 2.5, 2.5, 8.5, 8.5)
    assert not line_clear(t, 5.5, 5.5, 15.5, 5.5)


def test_astar_goes_through_the_gap():
    t = wall_map()
    path = find_path(t, (5.5, 5.5), (15.5, 5.5))
    assert path is not None and path[-1] == (15.5, 5.5)
    assert any(int(x) == 10 and int(y) == 17 for x, y in path)
    prev = (5.5, 5.5)
    for wp in path:  # every leg is walkable
        assert line_clear(t, *prev, *wp)
        prev = wp


def test_astar_returns_none_when_unreachable():
    tiles = np.full((20, 20), G, dtype=np.uint8)
    tiles[:, 10] = R
    assert find_path(TerrainMap(tiles), (5.5, 5.5), (15.5, 5.5)) is None


def test_astar_prefers_cheap_terrain():
    tiles = np.full((20, 20), G, dtype=np.uint8)
    tiles[8:13, 8:12] = Terrain.SWAMP  # a swamp patch that is cheaper to walk around
    path = find_path(TerrainMap(tiles), (4.5, 10.5), (15.5, 10.5))
    assert path is not None
    assert all(Terrain(tiles[int(y), int(x)]) is not Terrain.SWAMP for x, y in path)


def test_minion_walks_around_a_wall_to_food():
    sim = world(wall_map())
    tree = sim.forest.add(15, 5, Terrain.GRASS)
    m = sim.spawn_minion(5.5, 5.5, neutral_genome(speed=1.0, vision=1.0))
    m.age = m.maturity
    m.energy = m.traits.max_energy * 0.45  # hungry, but enough for the detour
    sim._rebuild_index()
    for _ in range(1000):
        sim.step()
        if m.fruits_eaten:
            break
    assert m.alive
    assert m.fruits_eaten == 1 and not tree.has_fruit


# ---------------------------------------------------------------- needs & brain


def test_maslow_gate_blocks_higher_levels_when_starving():
    n = Needs(hunger=0.05, rest=1, activity=1, safety=1, belonging=1, partner=1, status=1)
    assert n.gate(2) < 0.05 and n.gate(5) < 0.05
    n.hunger = 1.0
    assert n.gate(5) > 0.95


def _scores(sim, m, p=None):
    sim.rng.seed(0)
    return score_actions(m, sim, p or Perception())


def test_hungry_minion_prefers_food():
    sim = world()
    m = sim.spawn_minion(5, 5, neutral_genome())
    m.energy = m.traits.max_energy * 0.2
    s = _scores(sim, m)
    assert max(s, key=s.get) is Action.SEEK_FOOD


def test_threat_makes_minion_flee():
    sim = world()
    m = sim.spawn_minion(5, 5, neutral_genome(fearfulness=0.8))
    s = _scores(sim, m, Perception(threat=0.8, threat_pos=(6, 5)))
    assert max(s, key=s.get) is Action.FLEE


def test_minions_sleep_at_night_and_not_at_noon():
    sim = world()
    m = sim.spawn_minion(5, 5, neutral_genome())
    m.energy = m.traits.max_energy
    m.needs.rest = 0.5
    s = _scores(sim, m)
    assert max(s, key=s.get) is not Action.SLEEP
    sim.clock.tick = sim.config.ticks_per_day * 3  # midnight
    s = _scores(sim, m)
    assert max(s, key=s.get) is Action.SLEEP


def test_curious_minion_explores_when_content():
    sim = world()
    m = sim.spawn_minion(5, 5, neutral_genome(curiosity=1.0))
    m.energy = m.traits.max_energy
    m.needs = Needs(hunger=1, rest=1, activity=1, safety=1, belonging=1, partner=1, status=1)
    m.needs.fulfilment = 0.0
    s = _scores(sim, m)
    assert max(s, key=s.get) is Action.EXPLORE


def test_sleep_restores_rest_and_saves_energy():
    sim = world()
    sleeper = sim.spawn_minion(5, 5, neutral_genome())
    idle = sim.spawn_minion(15, 15, neutral_genome())
    sim.clock.tick = sim.config.ticks_per_day * 3  # midnight
    for m in (sleeper, idle):
        m.energy = m.traits.max_energy
        m.needs.rest = 0.2
    for _ in range(300):
        sleeper.action = Action.SLEEP
        idle.action = Action.REST
        for m in (sleeper, idle):
            m._moved = 0.0
            m.metabolise(sim)
        sim.clock.tick += 1
    assert sleeper.needs.rest > 0.6 > idle.needs.rest
    assert sleeper.energy > idle.energy


def test_standing_still_builds_restlessness():
    sim = world()
    m = sim.spawn_minion(5, 5, neutral_genome(activity_need=1.0))
    m.action = Action.REST
    for _ in range(sim.config.ticks_per_day // 4):
        m._moved = 0.0
        m.metabolise(sim)
        sim.clock.tick += 1
    assert m.needs.activity < 0.3


def test_visiting_new_regions_fulfils():
    sim = world()
    m = sim.spawn_minion(1, 1, neutral_genome())
    m.needs.fulfilment = 0.0
    m._update_needs(sim, 1)
    first = m.needs.fulfilment
    m.x = 15  # a different exploration region
    m._update_needs(sim, 1)
    assert first > 0 and m.needs.fulfilment > first


def test_full_day_runs_without_errors_and_the_well_fed_sleep_at_night():
    sim = Simulation(SimConfig(seed=2, map_width=50, map_height=40, initial_minions=40, initial_predators=0))
    tpd = sim.config.ticks_per_day
    while sim.tick < tpd * 2 + tpd // 24:  # 01:00 on the third day
        sim.step()
    # Hungry minions may forage at night, everyone else should be asleep.
    fed = [m for m in sim.minions if m.energy_frac > 0.6]
    assert fed
    assert sum(m.action is Action.SLEEP for m in fed) >= 0.9 * len(fed)
    assert all(sim.terrain.passable(m.x, m.y) for m in sim.minions)
