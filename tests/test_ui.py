"""Smoke tests for the pygame UI, run without a display."""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
import pygame_gui  # noqa: E402
import pytest  # noqa: E402

from lifesim.agents.minion import Minion  # noqa: E402
from lifesim.agents.predator import Predator  # noqa: E402
from lifesim.config import SimConfig  # noqa: E402
from lifesim.ui import charts  # noqa: E402
from lifesim.ui.app import HELP, INSPECTOR, OVERVIEW, SETTINGS, App  # noqa: E402
from lifesim.ui.panels.settings import LIVE_MINIONS, LIVE_PREDATORS, LIVE_WORLD, START  # noqa: E402


@pytest.fixture
def app():
    a = App(SimConfig(seed=3, map_width=60, map_height=40, initial_minions=30), size=(1100, 760))
    for _ in range(600):
        a.sim.step()
    yield a
    pygame.quit()


def pump(app):
    for event in pygame.event.get():
        app.handle_event(event)
    app.manager.update(0.05)


def click(app, pos):
    pygame.mouse.set_pos(pos)
    for kind in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
        app.handle_event(pygame.event.Event(kind, pos=pos, button=1))
    pump(app)


def test_every_tab_draws(app):
    for tab in (OVERVIEW, INSPECTOR, SETTINGS, HELP):
        app.show_tab(tab)
        app._draw()
    app.select(app.sim.minions[0])
    app._draw()
    app.select(app.sim.predators[0])
    app._draw()


def test_toolbar_buttons_work_with_the_mouse(app):
    click(app, app.btn_pause.rect.center)
    assert app.paused
    tick = app.sim.tick
    click(app, app.btn_step.rect.center)
    assert app.sim.tick == tick + 1
    click(app, app.btn_faster.rect.center)
    assert app.speed_idx == 3
    click(app, app.tab_buttons[HELP].rect.center)
    assert app.tab == HELP


def test_clicking_the_map_selects_and_opens_inspector(app):
    m = app.sim.minions[0]
    app.cam.zoom_at(4, 0, 0)
    app.cam.center_on(m.x, m.y)
    app._select_at(app.cam.world_to_screen(m.x, m.y))
    assert isinstance(app.selected, (Minion, Predator))
    assert app.tab == INSPECTOR


def test_inspector_links_select_relatives(app):
    child = next(m for m in app.sim.minions if m.parents and any(
        p.id in m.parents for p in app.sim.minions))  # fmt: skip
    app.select(child)
    app._draw()
    panel = app.panels[INSPECTOR]
    parent_ids = set(child.parents)
    for area, action in list(panel._links):
        action()
        if isinstance(app.selected, Minion) and app.selected.id in parent_ids:
            break
        app.select(child)
    assert app.selected.id in parent_ids


def test_live_slider_changes_running_simulation_but_start_slider_waits(app):
    sliders = {spec.key: widget for widget, (spec, _, _) in app.settings._sliders.items()}
    app.handle_event(pygame.event.Event(pygame_gui.UI_HORIZONTAL_SLIDER_MOVED,
                                        ui_element=sliders["mutation_rate"], value=0.333))  # fmt: skip
    assert app.sim.config.mutation_rate == pytest.approx(0.33)
    app.handle_event(pygame.event.Event(pygame_gui.UI_HORIZONTAL_SLIDER_MOVED,
                                        ui_element=sliders["initial_minions"], value=12.4))  # fmt: skip
    assert app.pending.initial_minions == 12 and isinstance(app.pending.initial_minions, int)
    assert app.sim.config.initial_minions == 30
    app.settings._restart()
    assert len(app.sim.minions) == 12
    assert app.sim.config.mutation_rate == pytest.approx(0.33)  # live values carry over


def test_settings_ranges_contain_defaults_and_whole_steps():
    defaults = SimConfig()
    for s in (*LIVE_WORLD, *LIVE_MINIONS, *LIVE_PREDATORS, *START):
        assert s.lo <= getattr(defaults, s.key) <= s.hi, s.key
        steps = (s.hi - s.lo) / s.step
        assert abs(steps - round(steps)) < 1e-6, s.key


def test_turbo_runs_many_ticks_per_frame(app):
    app.toggle_turbo()
    tick = app.sim.tick
    app._advance()
    assert app.sim.tick - tick > 64


def test_charts_handle_edge_cases():
    surface = pygame.Surface((300, 200))
    rect = pygame.Rect(0, 0, 300, 120)
    charts.line_chart(surface, rect, "leer", [], [], (255, 0, 0), None)
    charts.line_chart(surface, rect, "eins", [5], [0], (255, 0, 0), (100, 60))
    charts.line_chart(surface, rect, "null", [0, 0, 0], [0, 1, 2], (255, 0, 0), (100, 60))
    charts.sparkline(surface, pygame.Rect(0, 130, 140, 40), "gen", [0.5] * 500, (0, 0, 255), (50, 150))
    assert charts._nice_max(210) == 250 and charts._nice_max(7) == 10 and charts._nice_max(0) == 1


def test_save_load_and_export_from_the_ui(app, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F5, mod=0, unicode=""))
    assert (tmp_path / "saves" / "schnellspeicher.lifesim").exists()
    tick = app.sim.tick
    for _ in range(50):
        app.sim.step()
    app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F9, mod=0, unicode=""))
    assert app.sim.tick == tick
    app.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_e, mod=0, unicode=""))
    assert len(list((tmp_path / "exports").glob("*.csv"))) == 2
    app._draw()  # the notice overlay renders


def test_starting_a_preset_from_the_settings(app):
    panel = app.settings
    names = [p.name for p in panel._presets]
    panel._preset_index = names.index("paradies")
    panel._start_preset()
    assert app.sim.config.initial_predators == 0
    assert not app.sim.predators
