"""Main window: event loop, simulation pacing and a simple info side panel."""

from __future__ import annotations

import time

import pygame

from lifesim.agents.genome import GENE_NAMES, GENE_NAMES_DE
from lifesim.agents.minion import DeathCause, Minion
from lifesim.agents.needs import LEVEL_NAMES_DE
from lifesim.config import SimConfig
from lifesim.core.simulation import Simulation
from lifesim.ui.camera import Camera
from lifesim.ui.renderer import Renderer

PANEL_W = 300
SPEEDS = (0.25, 0.5, 1, 2, 4, 8, 16, 32, 64)
FPS = 60
PAN_SPEED_PX = 12
# Max wall time per frame spent simulating, so high speeds degrade gracefully instead of freezing.
SIM_BUDGET_S = 0.030

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
    "G          Farbe: Gene / Gruppe",
    "H          Hilfe ein/aus",
)


def satisfaction_color(v: float) -> tuple[int, int, int]:
    """Red (unsatisfied) through yellow to green (satisfied)."""
    red, yellow, green = (205, 70, 60), (230, 200, 70), (90, 190, 95)
    a, b, t = (red, yellow, v * 2) if v < 0.5 else (yellow, green, (v - 0.5) * 2)
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


class App:
    def __init__(self, config: SimConfig, size: tuple[int, int] = (1280, 800)) -> None:
        pygame.init()
        pygame.display.set_caption("Life-Simulator")
        self.screen = pygame.display.set_mode(size, pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("dejavusans,arial", 14)
        self.font_bold = pygame.font.SysFont("dejavusans,arial", 16, bold=True)
        self.font_small = pygame.font.SysFont("dejavusans,arial", 12)
        self.show_help = False
        self.config = config
        self.speed_idx = SPEEDS.index(1)
        self.paused = False
        self._tick_accum = 0.0
        self._ticks_this_second = 0
        self._tps_window_start = time.perf_counter()
        self.actual_tps = 0.0
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
        deadline = time.perf_counter() + SIM_BUDGET_S
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
        elif key == pygame.K_g:
            self.renderer.color_by_group = not self.renderer.color_by_group
        elif key == pygame.K_h:
            self.show_help = not self.show_help
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
        clock = sim.clock
        speed = SPEEDS[self.speed_idx]
        hist = sim.history[-1]
        line("Life-Simulator", bold=True)
        daytime = "Nacht" if clock.is_night else "Tag"
        line(f"Tag {clock.day + 1}, {clock.clock_text()} ({daytime}) · {clock.season_name}, J{clock.year + 1}")
        line(f"Tempo: {speed:g}x  ({self.actual_tps:.0f} Ticks/s)" + ("  PAUSE" if self.paused else ""))
        line(f"Minions: {len(sim.minions)}   Generation Ø {hist['mean_generation']:.1f}")
        line(f"Gruppen: {len(sim.groups)} (größte {hist['largest_group']})")
        line(f"Kämpfe: {sim.fights}   Geteilt: {sim.shares}")
        line(f"Raubtiere: {len(sim.predators)}")
        line(f"Gefressen: {sim.kills}   Vertrieben: {sim.repelled}")
        d = sim.deaths
        line(
            f"Geburten: {sim.births}   Tote: {d[DeathCause.STARVATION]}/{d[DeathCause.OLD_AGE]}/"
            f"{d[DeathCause.FIGHT]}/{d[DeathCause.PREDATOR]}"
        )
        line("(Hunger/Alter/Kampf/Raubtier)", color=(150, 150, 150))
        line(f"Bäume: {len(sim.forest.trees)}   Früchte: {sim.forest.fruit_count()}")
        y += 6

        m = self.selected
        if m is not None:
            tpd = sim.config.ticks_per_day
            rec = sim.lineage[m.id]
            status = "" if m.alive else f" (tot: {m.death_cause.value})"
            line(f"Minion #{m.id}{status}", bold=True)
            group = sim.groups.get(m.group_id)
            if group is not None:
                role = ", Anführer" if group.leader == m.id else f", Anführer #{group.leader}"
                self._draw_swatch(x, y, group.color)
                line(f"    Gruppe #{group.id} ({len(group.members)}){role}")
            else:
                line("Keine Gruppe", color=(170, 170, 170))
            line(f"Aktion: {m.action.value}")
            stage = "" if m.is_adult else ", jung"
            line(
                f"Energie {m.energy:.0f}/{m.traits.max_energy:.0f} · "
                f"Alter {m.age / tpd:.1f}/{m.max_age / tpd:.1f} T{stage}"
            )
            parents = f"#{rec.parents[0]} & #{rec.parents[1]}" if rec.parents else "Gründer"
            line(f"Generation {m.generation}, Eltern: {parents}")
            line(f"Kinder: {len(rec.children)}   Nachkommen: {sim.lineage.descendant_count(m.id)}")
            line(f"Früchte: {m.fruits_eaten}   Können: {m.skill:.0%}   Geteilt: {m.times_shared}")
            line(f"Kämpfe gewonnen/verloren: {m.fights_won}/{m.fights_lost}")
            ties = sim.relations.strongest(m.id, 2)
            line("Beziehungen: " + ("  ".join(f"#{o} {v:+.1f}" for o, v in ties) or "keine"))
            y = self._draw_pyramid(x, y + 4, m.needs.levels()) + 6
            row_h = self.font_small.get_linesize() + 1
            for g in GENE_NAMES:
                v = m.genome[g]
                self.screen.blit(self.font_small.render(GENE_NAMES_DE[g], True, (200, 200, 200)), (x, y))
                bar = pygame.Rect(x + 120, y + 3, 150, 9)
                pygame.draw.rect(self.screen, (60, 60, 66), bar)
                pygame.draw.rect(self.screen, (120, 180, 240), (bar.x, bar.y, bar.w * v, bar.h))
                y += row_h
            y += 6
        else:
            line("Klicke auf einen Minion.", color=(160, 160, 160))
            y += 6

        if self.show_help or m is None:
            line("Steuerung", bold=True)
            for text in HELP_LINES:
                line(text, color=(170, 170, 170))
        else:
            line("H: Steuerung anzeigen", color=(150, 150, 150))

    def _draw_swatch(self, x: int, y: int, color: tuple[int, int, int]) -> None:
        pygame.draw.circle(self.screen, color, (x + 8, y + 9), 6, 3)

    def _draw_pyramid(self, x: int, y: int, levels: tuple[float, ...]) -> int:
        """Maslow pyramid, bottom level widest, each tier coloured by its satisfaction."""
        tier_h, gap, base_w, shrink = 17, 2, PANEL_W - 24, 34
        top = y
        for i in reversed(range(len(levels))):
            w = base_w - i * shrink
            tier_y = top + (len(levels) - 1 - i) * (tier_h + gap)
            rect = pygame.Rect(x + (base_w - w) // 2, tier_y, w, tier_h)
            pygame.draw.rect(self.screen, satisfaction_color(levels[i]), rect, border_radius=3)
            label = self.font_small.render(LEVEL_NAMES_DE[i], True, (20, 20, 24))
            self.screen.blit(label, label.get_rect(center=rect.center))
        return top + len(levels) * (tier_h + gap)
