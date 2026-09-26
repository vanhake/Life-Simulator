"""Main window: map on the left, a side panel with toolbar and tabs on the right."""

from __future__ import annotations

import dataclasses
import time

import pygame
import pygame_gui
from pygame_gui.elements import UIButton, UILabel

from lifesim.agents.minion import Minion
from lifesim.agents.predator import Predator
from lifesim.config import SimConfig
from lifesim.core.simulation import Simulation
from lifesim.persistence import export
from lifesim.persistence import save as savefile
from lifesim.ui import theme
from lifesim.ui.camera import Camera
from lifesim.ui.gui_theme import GUI_THEME
from lifesim.ui.panels.help import HelpPanel
from lifesim.ui.panels.inspector import InspectorPanel
from lifesim.ui.panels.overview import OverviewPanel
from lifesim.ui.panels.settings import SettingsPanel
from lifesim.ui.renderer import Renderer

PANEL_W = 400
TOOLBAR_H = 86
SPEEDS = (0.25, 0.5, 1, 2, 4, 8, 16, 32, 64)
FPS = 60
PAN_SPEED_PX = 12
# Max wall time per frame spent simulating, so high speeds degrade gracefully instead of freezing.
SIM_BUDGET_S = 0.030
TURBO_BUDGET_S = 0.200  # turbo: simulate as much as fits, redraw only a few times a second
NOTICE_SECONDS = 4.0

TABS = ("Übersicht", "Minion", "Einstellungen", "Hilfe")
OVERVIEW, INSPECTOR, SETTINGS, HELP = range(4)

Selectable = Minion | Predator


class App:
    def __init__(self, config: SimConfig, size: tuple[int, int] = (1440, 880)) -> None:
        pygame.init()
        theme.reset_fonts()
        pygame.display.set_caption("Life-Simulator")
        self.screen = pygame.display.set_mode(size, pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        self.manager = pygame_gui.UIManager(size, GUI_THEME)
        self.pending = dataclasses.replace(config)  # settings for the next restart
        self.speed_idx = SPEEDS.index(1)
        self.paused = False
        self.turbo = False
        self.follow = False
        self.tab = OVERVIEW
        self._tick_accum = 0.0
        self._ticks_this_second = 0
        self._tps_window_start = time.perf_counter()
        self.actual_tps = 0.0
        self._dragging = False
        self.panels = {
            OVERVIEW: OverviewPanel(self),
            INSPECTOR: InspectorPanel(self),
            HELP: HelpPanel(self),
        }
        self.settings = SettingsPanel(self)
        self.selected: Selectable | None = None
        self._notice: tuple[str, float] | None = None
        self.restart(dataclasses.replace(config))

    # ------------------------------------------------------------------ setup

    def restart(self, config: SimConfig | None = None) -> None:
        if config is not None:
            self.config = config
        self._use(Simulation(dataclasses.replace(self.config)))

    def _use(self, sim: Simulation) -> None:
        """Show `sim` (new or loaded) with a fresh renderer, camera and widgets."""
        self.sim = sim
        self.renderer = Renderer(self.sim)
        mr = self.map_rect
        self.cam = Camera(mr.w, mr.h, self.sim.terrain.width, self.sim.terrain.height)
        self.selected = None
        self.follow = False
        self.rebuild_ui()

    @property
    def map_rect(self) -> pygame.Rect:
        w, h = self.screen.get_size()
        return pygame.Rect(0, 0, max(1, w - PANEL_W), h)

    @property
    def panel_rect(self) -> pygame.Rect:
        w, h = self.screen.get_size()
        return pygame.Rect(w - PANEL_W, 0, PANEL_W, h)

    @property
    def content_rect(self) -> pygame.Rect:
        p = self.panel_rect
        return pygame.Rect(p.x, p.y + TOOLBAR_H, p.w, p.h - TOOLBAR_H)

    def rebuild_ui(self) -> None:
        """(Re)create all pygame_gui widgets, e.g. after a restart or a window resize."""
        self.manager.clear_and_reset()
        self.manager.set_window_resolution(self.screen.get_size())
        p = self.panel_rect
        x, y = p.x + 10, p.y + 8
        self.btn_pause = UIButton(pygame.Rect(x, y, 96, 30), "", self.manager)
        self.btn_step = UIButton(pygame.Rect(x + 100, y, 70, 30), "Schritt", self.manager)
        self.btn_slower = UIButton(pygame.Rect(x + 174, y, 30, 30), "–", self.manager)
        self.lbl_speed = UILabel(pygame.Rect(x + 206, y, 50, 30), "", self.manager, object_id="#value")
        self.btn_faster = UIButton(pygame.Rect(x + 258, y, 30, 30), "+", self.manager)
        self.btn_turbo = UIButton(pygame.Rect(x + 292, y, 88, 30), "Turbo", self.manager)
        tab_w = (p.w - 20 - 3 * 4) // 4
        self.tab_buttons = [
            UIButton(pygame.Rect(x + i * (tab_w + 4), y + 40, tab_w, 30), name, self.manager)
            for i, name in enumerate(TABS)
        ]
        self.settings.build(self.manager, self.content_rect)
        self._sync_widgets()

    def _sync_widgets(self) -> None:
        self.btn_pause.set_text("Weiter" if self.paused else "Pause")
        if self.turbo:
            self.btn_turbo.select()
            self.lbl_speed.set_text("max")
        else:
            self.btn_turbo.unselect()
            self.lbl_speed.set_text(f"{SPEEDS[self.speed_idx]:g}x".replace(".", ","))
        for i, b in enumerate(self.tab_buttons):
            b.select() if i == self.tab else b.unselect()
        self.settings.show(self.tab == SETTINGS)

    # ------------------------------------------------------------------ files

    def save_game(self, path=None) -> None:
        path = savefile.save(self.sim, path or savefile.timestamped_path())
        self.settings.refresh_saves()
        self.notify(f"Gespeichert: {path}")

    def load_game(self, path) -> None:
        try:
            sim = savefile.load(path)
        except savefile.SaveError as e:
            self.notify(f"Laden fehlgeschlagen: {e}")
            return
        self.config = dataclasses.replace(sim.config)
        self.pending = dataclasses.replace(sim.config)
        self._use(sim)
        self.notify(f"Geladen: {path}")

    def export_csv(self) -> None:
        history, minions = export.export_all(self.sim)
        self.notify(f"Exportiert: {history.name} und {minions.name} in {history.parent}/")

    def notify(self, text: str) -> None:
        self._notice = (text, time.perf_counter() + NOTICE_SECONDS)

    # ------------------------------------------------------------------ public actions

    def select(self, obj: Selectable | None) -> None:
        self.selected = obj
        self.follow = False
        if obj is not None:
            self.show_tab(INSPECTOR)

    def toggle_follow(self) -> None:
        if self.selected is not None and self.selected.alive:
            self.follow = not self.follow

    def show_tab(self, tab: int) -> None:
        self.tab = tab
        self._sync_widgets()

    def toggle_pause(self) -> None:
        self.paused = not self.paused
        self._sync_widgets()

    def change_speed(self, delta: int) -> None:
        self.turbo = False
        self.speed_idx = max(0, min(len(SPEEDS) - 1, self.speed_idx + delta))
        self._sync_widgets()

    def toggle_turbo(self) -> None:
        self.turbo = not self.turbo
        self._sync_widgets()

    def step_once(self) -> None:
        if self.paused:
            self.sim.step()

    # ------------------------------------------------------------------ loop

    def run(self) -> None:
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                else:
                    self.handle_event(event)
            self.manager.update(dt)
            self._handle_held_keys()
            self._advance()
            self._draw()
        pygame.quit()

    def _advance(self) -> None:
        if self.paused:
            return
        if self.turbo:
            budget, self._tick_accum = TURBO_BUDGET_S, float("inf")
        else:
            budget = SIM_BUDGET_S
            self._tick_accum += SPEEDS[self.speed_idx]
        deadline = time.perf_counter() + budget
        while self._tick_accum >= 1:
            self._tick_accum -= 1
            self.sim.step()
            self._ticks_this_second += 1
            if time.perf_counter() > deadline:
                self._tick_accum = 0.0  # drop the backlog instead of accumulating lag
                break
        now = time.perf_counter()
        if now - self._tps_window_start >= 1.0:
            self.actual_tps = self._ticks_this_second / (now - self._tps_window_start)
            self._ticks_this_second = 0
            self._tps_window_start = now
        if self.selected is not None and not self.selected.alive:
            self.follow = False

    # ------------------------------------------------------------------ events

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.VIDEORESIZE:
            self.screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
            mr = self.map_rect
            self.cam.resize(mr.w, mr.h)
            self.rebuild_ui()
            return
        consumed = self.manager.process_events(event)
        if event.type == pygame_gui.UI_BUTTON_PRESSED:
            self._on_button(event.ui_element)
        self.settings.process_event(event)
        if consumed:
            return

        if event.type == pygame.KEYDOWN and not self.settings.typing:
            self._handle_key(event.key)
        elif event.type == pygame.MOUSEWHEEL:
            mx, my = pygame.mouse.get_pos()
            if self.map_rect.collidepoint(mx, my):
                self.cam.zoom_at(1.15**event.y, mx, my)
            elif self.content_rect.collidepoint(mx, my) and self.tab in self.panels:
                self.panels[self.tab].wheel(event.y)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and self.map_rect.collidepoint(event.pos):
                self._select_at(event.pos)
            elif event.button == 1 and self.content_rect.collidepoint(event.pos) and self.tab in self.panels:
                self.panels[self.tab].click(self.content_rect, event.pos)
            elif event.button == 3 and self.map_rect.collidepoint(event.pos):
                self._dragging = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 3:
            self._dragging = False
        elif event.type == pygame.MOUSEMOTION and self._dragging:
            self.follow = False
            self.cam.pan(-event.rel[0], -event.rel[1])

    def _on_button(self, element) -> None:
        actions = {
            self.btn_pause: self.toggle_pause,
            self.btn_step: self.step_once,
            self.btn_slower: lambda: self.change_speed(-1),
            self.btn_faster: lambda: self.change_speed(+1),
            self.btn_turbo: self.toggle_turbo,
        }
        if element in actions:
            actions[element]()
        elif element in self.tab_buttons:
            self.show_tab(self.tab_buttons.index(element))

    def _select_at(self, pos: tuple[int, int]) -> None:
        wx, wy = self.cam.screen_to_world(*pos)
        radius = max(0.8, 8 / self.cam.zoom)
        self.select(self.sim.predator_at(wx, wy, radius) or self.sim.minion_at(wx, wy, radius))

    def _handle_key(self, key: int) -> None:
        tab_keys = {pygame.K_1: OVERVIEW, pygame.K_2: INSPECTOR, pygame.K_3: SETTINGS, pygame.K_4: HELP}
        if key == pygame.K_SPACE:
            self.toggle_pause()
        elif key in (pygame.K_PLUS, pygame.K_KP_PLUS, pygame.K_EQUALS):
            self.change_speed(+1)
        elif key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self.change_speed(-1)
        elif key == pygame.K_t:
            self.toggle_turbo()
        elif key == pygame.K_n:
            self.step_once()
        elif key == pygame.K_r:
            self.restart()
        elif key == pygame.K_HOME:
            self.follow = False
            self.cam.fit()
        elif key == pygame.K_f:
            self.toggle_follow()
        elif key == pygame.K_g:
            self.renderer.color_by_group = not self.renderer.color_by_group
        elif key == pygame.K_F5:
            self.save_game(savefile.QUICKSAVE)
        elif key == pygame.K_F9:
            if savefile.QUICKSAVE.exists():
                self.load_game(savefile.QUICKSAVE)
            else:
                self.notify("Noch kein Schnellspeicher vorhanden (F5)")
        elif key == pygame.K_e:
            self.export_csv()
        elif key in tab_keys:
            self.show_tab(tab_keys[key])

    def _handle_held_keys(self) -> None:
        if self.settings.typing:
            return
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
        self.renderer.draw(self.screen.subsurface(self.map_rect), self.cam, self.selected)
        pygame.draw.rect(self.screen, theme.SURFACE, self.panel_rect)
        pygame.draw.line(self.screen, theme.GRID, self.panel_rect.topleft, self.panel_rect.bottomleft)
        if self.tab in self.panels:
            self.panels[self.tab].draw(self.screen, self.content_rect, pygame.mouse.get_pos())
        self._draw_status()
        self._draw_notice()
        self.manager.draw_ui(self.screen)
        pygame.display.flip()

    def _draw_notice(self) -> None:
        if self._notice is None:
            return
        text, until = self._notice
        if time.perf_counter() > until:
            self._notice = None
            return
        img = theme.font(14).render(text, True, theme.TEXT)
        box = img.get_rect().inflate(24, 14)
        mr = self.map_rect
        box.midbottom = (mr.centerx, mr.bottom - 20)
        pygame.draw.rect(self.screen, theme.SURFACE_RAISED, box, border_radius=6)
        pygame.draw.rect(self.screen, theme.GRID, box, 1, border_radius=6)
        self.screen.blit(img, img.get_rect(center=box.center))

    def _draw_status(self) -> None:
        """Speed and pause state as an overlay in the map's corner."""
        state = "PAUSE" if self.paused else f"{self.actual_tps:.0f} Ticks/s"
        img = theme.font(13).render(state, True, theme.TEXT)
        box = img.get_rect().inflate(12, 6)
        box.topleft = (8, 8)
        pygame.draw.rect(self.screen, theme.SURFACE, box, border_radius=4)
        self.screen.blit(img, img.get_rect(center=box.center))
