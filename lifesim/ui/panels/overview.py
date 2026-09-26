"""Overview tab: key figures, population charts and the evolution of every gene."""

from __future__ import annotations

import pygame

from lifesim.agents.genome import GENE_NAMES, GENE_NAMES_DE
from lifesim.agents.minion import DeathCause
from lifesim.ui import charts, theme
from lifesim.ui.panels.base import PAD, ScrollPanel


SERIES_KEYS = ("population", "predators", "groups", *(f"gene_{g}" for g in GENE_NAMES))


class OverviewPanel(ScrollPanel):
    def __init__(self, app) -> None:
        super().__init__(app)
        self._history_id: int | None = None
        self._series: dict[str, list[float]] = {}
        self._days: list[float] = []

    def _update_series(self) -> None:
        """Append only the new history rows instead of re-reading all of them every frame."""
        sim = self.app.sim
        if self._history_id != id(sim.history):  # a new simulation was started
            self._history_id = id(sim.history)
            self._series = {k: [] for k in SERIES_KEYS}
            self._days = []
        tpd = sim.config.ticks_per_day
        for row in sim.history[len(self._days) :]:
            self._days.append(row["tick"] / tpd)
            for k in SERIES_KEYS:
                self._series[k].append(row[k])

    def render(self, canvas: pygame.Surface, mouse: tuple[int, int] | None) -> int:
        sim = self.app.sim
        clock = sim.clock
        w = canvas.get_width()
        x, y = PAD, PAD
        last = sim.history[-1]

        daytime = "Nacht" if clock.is_night else "Tag"
        theme.text(canvas, f"Tag {clock.day + 1}, {clock.clock_text()} Uhr ({daytime})", (x, y), size=15, bold=True)
        y += 22
        theme.text(canvas, f"{clock.season_name}, Jahr {clock.year + 1}", (x, y), theme.TEXT_SECONDARY)
        y += 26

        d = sim.deaths
        figures = [
            ("Minions", f"{len(sim.minions)}"),
            ("Raubtiere", f"{len(sim.predators)}"),
            ("Gruppen", f"{len(sim.groups)} (größte {last['largest_group']})"),
            ("Generation Ø", f"{last['mean_generation']:.1f}".replace(".", ",")),
            ("Geburten", f"{sim.births}"),
            ("Bäume / Früchte", f"{len(sim.forest.trees)} / {sim.forest.fruit_count()}"),
            ("Kämpfe / Geteilt", f"{sim.fights} / {sim.shares}"),
            ("Gefressen / Vertrieben", f"{sim.kills} / {sim.repelled}"),
            ("Verhungert", f"{d[DeathCause.STARVATION]}"),
            ("Altersschwäche", f"{d[DeathCause.OLD_AGE]}"),
            ("Im Kampf gestorben", f"{d[DeathCause.FIGHT]}"),
            ("Gefressen worden", f"{d[DeathCause.PREDATOR]}"),
        ]
        for label, value in figures:
            theme.text(canvas, label, (x, y), theme.TEXT_SECONDARY, 13)
            theme.text(canvas, value, (w - PAD, y), theme.TEXT, 13, anchor="topright")
            y += 18
        y += 12

        self._update_series()
        series, days = self._series, self._days
        chart_w = w - 2 * PAD
        charts.line_chart(canvas, pygame.Rect(x, y, chart_w, 130), "Minions",
                          series["population"], days, theme.SERIES[0], mouse)  # fmt: skip
        y += 142
        charts.line_chart(canvas, pygame.Rect(x, y, chart_w, 100), "Raubtiere",
                          series["predators"], days, theme.SERIES[1], mouse)  # fmt: skip
        y += 112
        charts.line_chart(canvas, pygame.Rect(x, y, chart_w, 100), "Gruppen",
                          series["groups"], days, theme.SERIES[2], mouse)  # fmt: skip
        y += 118

        theme.text(canvas, "Evolution der Gene (Mittelwert, 0 bis 1)", (x, y), theme.TEXT, 13, bold=True)
        y += 22
        col_w = (chart_w - 16) // 2
        for i, gene in enumerate(GENE_NAMES):
            cx = x + (i % 2) * (col_w + 16)
            cy = y + (i // 2) * 46
            charts.sparkline(canvas, pygame.Rect(cx, cy, col_w, 40), GENE_NAMES_DE[gene],
                             series[f"gene_{gene}"], theme.SERIES[0], mouse)  # fmt: skip
        y += ((len(GENE_NAMES) + 1) // 2) * 46
        return y + PAD
