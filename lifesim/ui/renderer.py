"""Draws the world (terrain, trees, minions) through the camera."""

from __future__ import annotations

import colorsys
import math

import pygame

from lifesim.agents.minion import Action, Minion
from lifesim.core.simulation import Simulation
from lifesim.ui.camera import Camera
from lifesim.world.terrain import Terrain

TERRAIN_COLORS = {
    Terrain.GRASS: (118, 170, 86),
    Terrain.FOREST: (62, 122, 60),
    Terrain.SWAMP: (92, 110, 78),
    Terrain.MOUNTAIN: (140, 128, 110),
    Terrain.ROCK: (88, 84, 82),
}
TREE_COLOR = (34, 88, 36)
FRUIT_COLOR = (230, 60, 50)
SELECT_COLOR = (255, 255, 255)
ACTION_COLORS = {
    Action.WANDER: None,
    Action.SEEK_FOOD: (255, 210, 60),
    Action.EAT: (255, 120, 60),
}

TERRAIN_TILE_PX = 8  # resolution of the cached terrain image


def minion_color(m: Minion) -> tuple[int, int, int]:
    """Colour from the genome, so related minions look alike."""
    g = m.genome
    hue = (0.55 * g["aggression"] + 0.25 * g["sociability"] + 0.2 * g["curiosity"] + 0.5) % 1.0
    lightness = 0.35 + 0.35 * g["speed"]
    r, gg, b = colorsys.hls_to_rgb(hue, lightness, 0.75)
    return int(r * 255), int(gg * 255), int(b * 255)


class Renderer:
    def __init__(self, sim: Simulation) -> None:
        self.sim = sim
        self.terrain_surface = self._build_terrain_surface()

    def _build_terrain_surface(self) -> pygame.Surface:
        t = self.sim.terrain
        small = pygame.Surface((t.width, t.height))
        for y in range(t.height):
            for x in range(t.width):
                small.set_at((x, y), TERRAIN_COLORS[Terrain(int(t.tiles[y, x]))])
        return pygame.transform.scale(small, (t.width * TERRAIN_TILE_PX, t.height * TERRAIN_TILE_PX))

    def draw(self, surface: pygame.Surface, cam: Camera, selected: Minion | None) -> None:
        surface.fill((20, 22, 26))
        self._draw_terrain(surface, cam)

        vx, vy, vw, vh = cam.visible_rect()
        z = cam.zoom

        def visible(x: float, y: float) -> bool:
            return vx - 1 <= x <= vx + vw + 1 and vy - 1 <= y <= vy + vh + 1

        tree_r = max(1, int(0.4 * z))
        fruit_r = max(1, int(0.18 * z))
        for tree in self.sim.forest.trees:
            if not visible(tree.x, tree.y):
                continue
            sx, sy = cam.world_to_screen(tree.x, tree.y)
            pygame.draw.circle(surface, TREE_COLOR, (sx, sy), tree_r)
            if tree.has_fruit:
                pygame.draw.circle(surface, FRUIT_COLOR, (sx + tree_r * 0.3, sy - tree_r * 0.3), fruit_r)

        for m in self.sim.minions:
            if not visible(m.x, m.y):
                continue
            sx, sy = cam.world_to_screen(m.x, m.y)
            r = max(3, int(m.traits.size * z))
            pygame.draw.circle(surface, minion_color(m), (sx, sy), r)
            pygame.draw.circle(surface, (15, 15, 15), (sx, sy), r, 1)
            if z >= 10:
                # heading tick
                hx = sx + math.cos(m.heading) * r
                hy = sy + math.sin(m.heading) * r
                pygame.draw.line(surface, (15, 15, 15), (sx, sy), (hx, hy), 1)
                # energy bar
                w = r * 2
                pygame.draw.rect(surface, (40, 40, 40), (sx - r, sy - r - 5, w, 3))
                pygame.draw.rect(surface, (80, 220, 90), (sx - r, sy - r - 5, w * m.energy_frac, 3))
            ac = ACTION_COLORS[m.action]
            if ac is not None:
                pygame.draw.circle(surface, ac, (sx + r, sy - r), max(2, r // 3))

        if selected is not None and selected.alive:
            sx, sy = cam.world_to_screen(selected.x, selected.y)
            pygame.draw.circle(surface, SELECT_COLOR, (sx, sy), max(4, int(selected.traits.size * z) + 4), 2)
            vr = selected.traits.vision * z
            if vr < 4000:
                pygame.draw.circle(surface, (255, 255, 255), (sx, sy), vr, 1)
            if selected.target is not None:
                tx, ty = cam.world_to_screen(*selected.target)
                pygame.draw.line(surface, (255, 255, 255), (sx, sy), (tx, ty), 1)

    def _draw_terrain(self, surface: pygame.Surface, cam: Camera) -> None:
        vx, vy, vw, vh = cam.visible_rect()
        t = self.sim.terrain
        # Clip the visible world rect to the map and blit the matching part of the cached image.
        x0, y0 = max(0.0, vx), max(0.0, vy)
        x1, y1 = min(float(t.width), vx + vw), min(float(t.height), vy + vh)
        if x1 <= x0 or y1 <= y0:
            return
        src = pygame.Rect(
            int(x0 * TERRAIN_TILE_PX),
            int(y0 * TERRAIN_TILE_PX),
            max(1, int((x1 - x0) * TERRAIN_TILE_PX)),
            max(1, int((y1 - y0) * TERRAIN_TILE_PX)),
        ).clip(self.terrain_surface.get_rect())
        # Recompute destination from the integer source rect to avoid drift while zooming.
        sx0, sy0 = cam.world_to_screen(src.x / TERRAIN_TILE_PX, src.y / TERRAIN_TILE_PX)
        dw = src.w / TERRAIN_TILE_PX * cam.zoom
        dh = src.h / TERRAIN_TILE_PX * cam.zoom
        part = self.terrain_surface.subsurface(src)
        scaled = pygame.transform.scale(part, (max(1, round(dw)), max(1, round(dh))))
        surface.blit(scaled, (round(sx0), round(sy0)))
