"""Main window: event loop, simulation pacing and a simple info side panel."""

from __future__ import annotations

import pygame

from lifesim.agents.genome import GENE_NAMES, GENE_NAMES_DE
from lifesim.agents.minion import Minion
from lifesim.config import SimConfig
from lifesim.core.simulation import Simulation
from lifesim.ui.camera import Camera
from lifesim.ui.renderer import Renderer

PANEL_W = 300
SPEEDS = (0.25, 0.5, 1, 2, 4, 8, 16, 32, 64)
FPS = 60
PAN_SPEED_PX = 12

HELP_LINES = (
    "Leertaste  Pause / Weiter",
    "+ / -      Tempo",
    "N          Einzelschritt",
    "WASD/Pfeile Karte bewegen",
    "Rechte Maus Karte ziehen",
    "Mausrad    Zoom",
    "Linksklick Minion auswählen",
    "F          Ausgewähltem Minion folgen",
    "Pos1       Ganze Karte zeigen",
    "R          Neustart",
)


class App:
    def __init__(self, config: SimConfig, size: tuple[int, int] = (1280, 800)) -> None:
        pygame.init()
        pygame.display.set_caption("Life-Simulator")
        self.screen = pygame.display.set_mode(size, pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("dejavusans,arial", 14)
        self.font_bold = pygame.font.SysFont("dejavusans,arial", 16, bold=True)
        self.config = config
        self.speed_idx = SPEEDS.index(1)
        self.paused = False
        self._tick_accum = 0.0
        self.follow = False
        self._dragging = False
        self.restart()

    # ------------------------------------------------------------------ setup

    def restart(self) -> None:
        self.sim = Simulation(self.config)
        self.renderer = Renderer(self.sim)
        w, h = self.screen.get_size()
        self.cam = Camera(w - PANEL_W, h, self.sim.terrain.width, self.sim.terrain.height)
        self.selected: Minion | None = None

    @property
    def map_rect(self) -> pygame.Rect:
        w, h = self.screen.get_size()
        return pygame.Rect(0, 0, w - PANEL_W, h)

    # ------------------------------------------------------------------ loop

    def run(self) -> None:
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                else:
                    self.handle_event(event)
            self._handle_held_keys()
            self._advance()
            self._draw()
            self.clock.tick(FPS)
        pygame.quit()

    def _advance(self) -> None:
        if self.paused:
            return
        self._tick_accum += SPEEDS[self.speed_idx]
        while self._tick_accum >= 1:
            self._tick_accum -= 1
            self.sim.step()
        if self.selected is not None and not self.selected.alive:
            self.follow = False

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.VIDEORESIZE:
            self.cam.resize(max(1, event.w - PANEL_W), event.h)
        elif event.type == pygame.KEYDOWN:
            self._handle_key(event.key)
        elif event.type == pygame.MOUSEWHEEL:
            mx, my = pygame.mouse.get_pos()
            if self.map_rect.collidepoint(mx, my):
                self.cam.zoom_at(1.15 ** event.y, mx, my)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and self.map_rect.collidepoint(event.pos):
                wx, wy = self.cam.screen_to_world(*event.pos)
                self.selected = self.sim.minion_at(wx, wy, radius=max(0.8, 8 / self.cam.zoom))
            elif event.button == 3:
                self._dragging = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 3:
            self._dragging = False
        elif event.type == pygame.MOUSEMOTION and self._dragging:
            self.follow = False
            self.cam.pan(-event.rel[0], -event.rel[1])

    def _handle_key(self, key: int) -> None:
        if key == pygame.K_SPACE:
            self.paused = not self.paused
        elif key in (pygame.K_PLUS, pygame.K_KP_PLUS, pygame.K_EQUALS):
            self.speed_idx = min(len(SPEEDS) - 1, self.speed_idx + 1)
        elif key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self.speed_idx = max(0, self.speed_idx - 1)
        elif key == pygame.K_n and self.paused:
            self.sim.step()
        elif key == pygame.K_r:
            self.restart()
        elif key == pygame.K_HOME:
            self.follow = False
            self.cam.fit()
        elif key == pygame.K_f and self.selected is not None:
            self.follow = not self.follow

    def _handle_held_keys(self) -> None:
        keys = pygame.key.get_pressed()
        dx = (keys[pygame.K_d] or keys[pygame.K_RIGHT]) - (keys[pygame.K_a] or keys[pygame.K_LEFT])
        dy = (keys[pygame.K_s] or keys[pygame.K_DOWN]) - (keys[pygame.K_w] or keys[pygame.K_UP])
        if dx or dy:
            self.follow = False
            self.cam.pan(dx * PAN_SPEED_PX, dy * PAN_SPEED_PX)
        if self.follow and self.selected is not None and self.selected.alive:
            self.cam.center_on(self.selected.x, self.selected.y)

    # ------------------------------------------------------------------ drawing

    def _draw(self) -> None:
        map_surface = self.screen.subsurface(self.map_rect)
        self.renderer.draw(map_surface, self.cam, self.selected)
        self._draw_panel()
        pygame.display.flip()

    def _draw_panel(self) -> None:
        w, h = self.screen.get_size()
        panel = pygame.Rect(w - PANEL_W, 0, PANEL_W, h)
        pygame.draw.rect(self.screen, (32, 34, 40), panel)
        x, y = panel.x + 12, 12

        def line(text: str, bold: bool = False, color=(225, 225, 225)) -> None:
            nonlocal y
            font = self.font_bold if bold else self.font
            self.screen.blit(font.render(text, True, color), (x, y))
            y += font.get_linesize() + 2

        sim = self.sim
        speed = SPEEDS[self.speed_idx]
        line("Life-Simulator", bold=True)
        line(f"Tick: {sim.tick}")
        line(f"Tempo: {speed:g}x" + ("  (PAUSE)" if self.paused else ""))
        line(f"FPS: {self.clock.get_fps():.0f}")
        line(f"Minions: {len(sim.minions)}   Tote: {sim.deaths}")
        line(f"Bäume: {len(sim.forest.trees)}   Früchte: {sim.forest.fruit_count()}")
        y += 8

        m = self.selected
        if m is not None:
            line(f"Minion #{m.id}" + ("" if m.alive else " (tot)"), bold=True)
            line(f"Aktion: {m.action.value}")
            line(f"Energie: {m.energy:.0f} / {m.traits.max_energy:.0f}")
            line(f"Alter: {m.age}   Generation: {m.generation}")
            line(f"Früchte gegessen: {m.fruits_eaten}")
            for g in GENE_NAMES:
                v = m.genome[g]
                label = GENE_NAMES_DE[g]
                self.screen.blit(self.font.render(label, True, (200, 200, 200)), (x, y))
                bar = pygame.Rect(x + 140, y + 4, 130, 10)
                pygame.draw.rect(self.screen, (60, 60, 66), bar)
                pygame.draw.rect(self.screen, (120, 180, 240), (bar.x, bar.y, bar.w * v, bar.h))
                y += self.font.get_linesize() + 1
            y += 8
        else:
            line("Klicke auf einen Minion.", color=(160, 160, 160))
            y += 8

        line("Steuerung", bold=True)
        for text in HELP_LINES:
            line(text, color=(170, 170, 170))
