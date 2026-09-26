"""Draws the world (terrain, trees, minions) through the camera."""

from __future__ import annotations

import colorsys
import math

import pygame

from lifesim.agents.minion import Action, Minion
from lifesim.agents.predator import Predator, PredatorState
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
SAPLING_COLOR = (70, 130, 60)
FRUIT_COLOR = (230, 60, 50)
SELECT_COLOR = (255, 255, 255)
ACTION_COLORS = {
    Action.REST: None,
    Action.WANDER: None,
    Action.SEEK_FOOD: (255, 210, 60),
    Action.EAT: (255, 120, 60),
    Action.SLEEP: (120, 140, 255),
    Action.FLEE: (255, 40, 40),
    Action.SOCIALIZE: (90, 230, 230),
    Action.SEEK_MATE: (255, 110, 200),
    Action.EXPLORE: (190, 255, 120),
    Action.FIGHT: (255, 0, 0),
    Action.SHARE: (120, 255, 160),
}
CROWN_COLOR = (255, 215, 0)
NO_GROUP_COLOR = (150, 150, 150)
PREDATOR_COLORS = {
    PredatorState.HUNT: (255, 30, 30),
    PredatorState.WANDER: (200, 40, 40),
    PredatorState.REST: (120, 30, 30),
    PredatorState.RETREAT: (255, 150, 40),
}
NIGHT_COLOR = (10, 16, 48)
NIGHT_MAX_ALPHA = 150
WINTER_COLOR = (225, 235, 255, 45)

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
        self.color_by_group = False  # colour minions by group instead of by genes
        self.terrain_surface = self._build_terrain_surface()

    def _build_terrain_surface(self) -> pygame.Surface:
        t = self.sim.terrain
        small = pygame.Surface((t.width, t.height))
        for y in range(t.height):
            for x in range(t.width):
                small.set_at((x, y), TERRAIN_COLORS[Terrain(int(t.tiles[y, x]))])
        return pygame.transform.scale(small, (t.width * TERRAIN_TILE_PX, t.height * TERRAIN_TILE_PX))

    def draw(
        self, surface: pygame.Surface, cam: Camera, selected: Minion | Predator | None
    ) -> None:
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
            if tree.is_sapling:
                pygame.draw.circle(surface, SAPLING_COLOR, (sx, sy), max(1, tree_r // 2))
                continue
            pygame.draw.circle(surface, TREE_COLOR, (sx, sy), tree_r)
            if tree.has_fruit:
                pygame.draw.circle(surface, FRUIT_COLOR, (sx + tree_r * 0.3, sy - tree_r * 0.3), fruit_r)

        groups = self.sim.groups
        for m in self.sim.minions:
            if not visible(m.x, m.y):
                continue
            sx, sy = cam.world_to_screen(m.x, m.y)
            r = max(2 if m.is_adult else 1, int(m.traits.size * m.growth * z)) + 1
            group = groups.get(m.group_id)
            if group is not None:
                pygame.draw.circle(surface, group.color, (sx, sy), r + 2, 2)
            if self.color_by_group:
                body = group.color if group is not None else NO_GROUP_COLOR
            else:
                body = minion_color(m)
            pygame.draw.circle(surface, body, (sx, sy), r)
            pygame.draw.circle(surface, (15, 15, 15), (sx, sy), r, 1)
            if group is not None and group.leader == m.id:
                self._draw_crown(surface, sx, sy - r - 7, max(3, r))
            if z >= 10:
                # heading tick
                hx = sx + math.cos(m.heading) * r
                hy = sy + math.sin(m.heading) * r
                pygame.draw.line(surface, (15, 15, 15), (sx, sy), (hx, hy), 1)
                # energy bar
                w = r * 2
                pygame.draw.rect(surface, (40, 40, 40), (sx - r, sy - r - 5, w, 3))
                pygame.draw.rect(surface, (80, 220, 90), (sx - r, sy - r - 5, w * m.energy_frac, 3))
            ac = ACTION_COLORS.get(m.action)
            if ac is not None:
                pygame.draw.circle(surface, ac, (sx + r, sy - r), max(2, r // 3))

        self._draw_daylight(surface, cam)
        # Predators are drawn on top of the night tint so the viewer can follow the hunt.
        for p in self.sim.predators:
            if visible(p.x, p.y):
                self._draw_predator(surface, cam, p)

        if selected is not None and selected.alive:
            sx, sy = cam.world_to_screen(selected.x, selected.y)
            if isinstance(selected, Predator):
                radius, vision = 0.7, self.sim.config.predator_vision
            else:
                radius, vision = selected.traits.size + 0.1, selected.vision(self.sim)
            pygame.draw.circle(surface, SELECT_COLOR, (sx, sy), max(5, int(radius * z) + 4), 2)
            vr = vision * z
            if vr < 4000:
                pygame.draw.circle(surface, (255, 255, 255), (sx, sy), vr, 1)
            if selected.path:
                points = [(sx, sy)] + [cam.world_to_screen(*wp) for wp in selected.path]
                pygame.draw.lines(surface, (255, 255, 255), False, points, 1)

    @staticmethod
    def _draw_predator(surface: pygame.Surface, cam: Camera, p: Predator) -> None:
        sx, sy = cam.world_to_screen(p.x, p.y)
        size = max(4.0, 0.6 * cam.zoom)
        a = p.heading
        tip = (sx + math.cos(a) * size, sy + math.sin(a) * size)
        left = (sx + math.cos(a + 2.5) * size * 0.8, sy + math.sin(a + 2.5) * size * 0.8)
        right = (sx + math.cos(a - 2.5) * size * 0.8, sy + math.sin(a - 2.5) * size * 0.8)
        pygame.draw.polygon(surface, PREDATOR_COLORS[p.state], (tip, left, right))
        pygame.draw.polygon(surface, (20, 0, 0), (tip, left, right), 1)
        if cam.zoom >= 10:
            w = size * 2
            pygame.draw.rect(surface, (40, 40, 40), (sx - size, sy - size - 6, w, 3))
            pygame.draw.rect(surface, (230, 60, 60), (sx - size, sy - size - 6, w * p.energy_frac, 3))

    @staticmethod
    def _draw_crown(surface: pygame.Surface, cx: float, base_y: float, size: int) -> None:
        w, h = size * 1.4, size * 0.9
        left, right = cx - w / 2, cx + w / 2
        points = [
            (left, base_y), (left, base_y - h), (cx - w / 4, base_y - h / 2),
            (cx, base_y - h), (cx + w / 4, base_y - h / 2), (right, base_y - h), (right, base_y),
        ]  # fmt: skip
        pygame.draw.polygon(surface, CROWN_COLOR, points)
        pygame.draw.polygon(surface, (60, 45, 0), points, 1)

    def _draw_daylight(self, surface: pygame.Surface, cam: Camera) -> None:
        # Tint only the map itself, not the letterbox around it.
        x0, y0 = cam.world_to_screen(0, 0)
        x1, y1 = cam.world_to_screen(self.sim.terrain.width, self.sim.terrain.height)
        area = pygame.Rect(round(x0), round(y0), round(x1 - x0), round(y1 - y0)).clip(
            surface.get_rect()
        )
        if area.w <= 0 or area.h <= 0:
            return
        clock = self.sim.clock
        tints = []
        if clock.season == 3:
            tints.append(WINTER_COLOR)
        alpha = int((1.0 - clock.daylight) * NIGHT_MAX_ALPHA)
        if alpha > 0:
            tints.append((*NIGHT_COLOR, alpha))
        for color in tints:
            overlay = pygame.Surface(area.size, pygame.SRCALPHA)
            overlay.fill(color)
            surface.blit(overlay, area.topleft)

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
