"""Settings tab: live parameters take effect immediately, start parameters on restart."""

from __future__ import annotations

import dataclasses
import random
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pygame
import pygame_gui
from pygame_gui.elements import (
    UIButton,
    UIHorizontalSlider,
    UILabel,
    UIScrollingContainer,
    UITextEntryLine,
)

from lifesim.agents.genome import Genome
from lifesim.config import SimConfig

if TYPE_CHECKING:
    from lifesim.ui.app import App

PAD = 12
ROW_H = 48
SCROLLBAR_W = 20


@dataclass(frozen=True)
class Setting:
    key: str
    label: str
    lo: float
    hi: float
    step: float
    decimals: int = 0


LIVE_WORLD = (
    Setting("fruit_energy", "Energie pro Frucht", 5, 80, 1),
    Setting("fruit_regrow_ticks", "Nachwachszeit einer Frucht (Ticks)", 200, 4000, 50),
    Setting("tree_seed_chance_per_day", "Aussaat der Bäume pro Tag", 0, 1, 0.05, 2),
    Setting("night_vision_factor", "Sicht bei Nacht (Anteil)", 0.1, 1, 0.05, 2),
)
LIVE_MINIONS = (
    Setting("hunger_threshold", "Hungerschwelle (Anteil Energie)", 0.2, 0.9, 0.05, 2),
    Setting("mate_energy_threshold", "Energie für Paarung (Anteil)", 0.4, 0.95, 0.05, 2),
    Setting("mutation_rate", "Mutationsrate", 0, 1, 0.01, 2),
    Setting("mutation_strength", "Mutationsstärke", 0, 0.5, 0.01, 2),
    Setting("max_population", "Höchstzahl Minions", 50, 1000, 10),
)
LIVE_PREDATORS = (
    Setting("predator_speed", "Tempo (Kacheln pro Tick)", 0.03, 0.15, 0.005, 3),
    Setting("predator_kill_energy", "Energie pro Beute", 20, 200, 5),
    Setting("predator_drain", "Grundverbrauch pro Tick", 0.01, 0.15, 0.005, 3),
    Setting("predator_repel_power", "Nötige Abwehrkraft der Gruppe", 0.5, 5, 0.1, 1),
    Setting("predator_breed_cooldown_days", "Pause zwischen Nachwuchs (Tage)", 1, 15, 0.5, 1),
    Setting("max_predators", "Höchstzahl Raubtiere", 0, 50, 1),
)
START = (
    Setting("initial_minions", "Minions beim Start", 2, 400, 1),
    Setting("initial_predators", "Raubtiere beim Start", 0, 30, 1),
    Setting("map_width", "Kartenbreite (Kacheln)", 40, 300, 10),
    Setting("map_height", "Kartenhöhe (Kacheln)", 30, 200, 10),
    Setting("tree_density", "Baumdichte", 0.005, 0.15, 0.005, 3),
    Setting("ticks_per_day", "Ticks pro Tag", 600, 6000, 100),
    Setting("days_per_season", "Tage pro Jahreszeit", 1, 15, 1),
)


def _fmt(value: float, decimals: int) -> str:
    return f"{value:.{decimals}f}".replace(".", ",")


class SettingsPanel:
    """Built from pygame_gui elements inside a scrolling container."""

    def __init__(self, app: "App") -> None:
        self.app = app
        self.container: UIScrollingContainer | None = None
        self._sliders: dict[UIHorizontalSlider, tuple[Setting, UILabel, bool]] = {}
        self._buttons: dict[UIButton, Callable[[], None]] = {}
        self.seed_entry: UITextEntryLine | None = None
        self._immigration_button: UIButton | None = None

    # ------------------------------------------------------------------ building

    def build(self, manager: pygame_gui.UIManager, rect: pygame.Rect) -> None:
        self._sliders.clear()
        self._buttons.clear()
        self.container = UIScrollingContainer(rect, manager, allow_scroll_x=False)
        inner_w = rect.w - SCROLLBAR_W - 2 * PAD
        y = PAD

        def section(title: str, note: str | None = None) -> None:
            nonlocal y
            UILabel(pygame.Rect(PAD, y, inner_w, 24), title, manager, container=self.container,
                    object_id="#section")  # fmt: skip
            y += 26
            if note:
                UILabel(pygame.Rect(PAD, y, inner_w, 20), note, manager, container=self.container,
                        object_id="#note")  # fmt: skip
                y += 22

        def slider(s: Setting, live: bool) -> None:
            nonlocal y
            source = self.app.sim.config if live else self.app.pending
            value = getattr(source, s.key)
            UILabel(pygame.Rect(PAD, y, inner_w - 70, 22), s.label, manager, container=self.container)
            label = UILabel(pygame.Rect(PAD + inner_w - 70, y, 70, 22), _fmt(value, s.decimals), manager,
                            container=self.container, object_id="#value")  # fmt: skip
            widget = UIHorizontalSlider(pygame.Rect(PAD, y + 22, inner_w, 20), float(value), (s.lo, s.hi),
                                        manager, container=self.container, click_increment=s.step)  # fmt: skip
            self._sliders[widget] = (s, label, live)
            y += ROW_H

        def buttons(*entries: tuple[str, Callable[[], None]]) -> list[UIButton]:
            nonlocal y
            made = []
            w = (inner_w - 8 * (len(entries) - 1)) // len(entries)
            for i, (text, action) in enumerate(entries):
                b = UIButton(pygame.Rect(PAD + i * (w + 8), y, w, 30), text, manager, container=self.container)
                self._buttons[b] = action
                made.append(b)
            y += 40
            return made

        section("Welt", "Wirkt sofort")
        for s in LIVE_WORLD:
            slider(s, live=True)
        y += 6
        section("Minions", "Wirkt sofort")
        for s in LIVE_MINIONS:
            slider(s, live=True)
        buttons(("+10 Minions", self._add_minions))
        y += 6
        section("Raubtiere", "Wirkt sofort")
        for s in LIVE_PREDATORS:
            slider(s, live=True)
        self._immigration_button, _ = buttons(
            (self._immigration_text(), self._toggle_immigration), ("+2 Raubtiere", self._add_predators)
        )
        y += 6
        section("Neue Welt", "Wirkt beim Neustart")
        UILabel(pygame.Rect(PAD, y, 70, 30), "Seed", manager, container=self.container)
        self.seed_entry = UITextEntryLine(pygame.Rect(PAD + 70, y, inner_w - 70, 30), manager,
                                          container=self.container)  # fmt: skip
        self.seed_entry.set_allowed_characters("numbers")
        self.seed_entry.set_text(str(self.app.pending.seed))
        y += 40
        for s in START:
            slider(s, live=False)
        buttons(("Zufälliger Seed", self._random_seed), ("Standardwerte", self._defaults))
        buttons(("Neustart mit diesen Werten", self._restart))
        self.container.set_scrollable_area_dimensions((rect.w - SCROLLBAR_W, y + PAD))

    def show(self, visible: bool) -> None:
        if self.container is not None:
            self.container.show() if visible else self.container.hide()

    @property
    def typing(self) -> bool:
        return self.seed_entry is not None and self.seed_entry.is_focused

    # ------------------------------------------------------------------ events

    def process_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame_gui.UI_HORIZONTAL_SLIDER_MOVED and event.ui_element in self._sliders:
            s, label, live = self._sliders[event.ui_element]
            value = round(event.value / s.step) * s.step
            is_int = isinstance(getattr(SimConfig(), s.key), int)
            value = int(round(value)) if is_int else round(value, 6)
            label.set_text(_fmt(value, s.decimals))
            setattr(self.app.pending, s.key, value)
            if live:
                setattr(self.app.sim.config, s.key, value)
        elif event.type == pygame_gui.UI_BUTTON_PRESSED and event.ui_element in self._buttons:
            self._buttons[event.ui_element]()
        elif event.type == pygame_gui.UI_TEXT_ENTRY_FINISHED and event.ui_element is self.seed_entry:
            self._read_seed()

    def _read_seed(self) -> None:
        text = self.seed_entry.get_text() if self.seed_entry else ""
        if text.isdigit():
            self.app.pending.seed = int(text)

    # ------------------------------------------------------------------ actions

    def _restart(self) -> None:
        self._read_seed()
        self.app.restart(dataclasses.replace(self.app.pending))

    def _random_seed(self) -> None:
        self.app.pending.seed = random.randrange(1, 1_000_000)
        if self.seed_entry is not None:
            self.seed_entry.set_text(str(self.app.pending.seed))

    def _defaults(self) -> None:
        defaults = SimConfig()
        defaults.seed = self.app.pending.seed
        self.app.pending = defaults
        self.app.rebuild_ui()

    def _add_minions(self) -> None:
        sim = self.app.sim
        for _ in range(10):
            m = sim.spawn_minion(*sim.random_passable_point(), Genome.random(sim.rng))
            m.age = m.maturity

    def _add_predators(self) -> None:
        sim = self.app.sim
        for _ in range(2):
            sim.spawn_predator(*sim.random_passable_point())

    def _immigration_text(self) -> str:
        on = self.app.sim.config.predator_immigration
        return f"Zuwanderung: {'an' if on else 'aus'}"

    def _toggle_immigration(self) -> None:
        cfg = self.app.sim.config
        cfg.predator_immigration = not cfg.predator_immigration
        self.app.pending.predator_immigration = cfg.predator_immigration
        if self._immigration_button is not None:
            self._immigration_button.set_text(self._immigration_text())

