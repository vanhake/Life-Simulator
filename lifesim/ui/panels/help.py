"""Help tab: keyboard shortcuts and a legend of the symbols on the map."""

from __future__ import annotations

import pygame

from lifesim.agents.brain import Action
from lifesim.agents.predator import PredatorState
from lifesim.ui import theme
from lifesim.ui.panels.base import PAD, ScrollPanel
from lifesim.ui.renderer import ACTION_COLORS, CROWN_COLOR, PREDATOR_COLORS

SHORTCUTS = (
    ("Leertaste", "Pause / Weiter"),
    ("+ / -", "Tempo (0,25x bis 64x)"),
    ("T", "Turbo: so schnell wie möglich"),
    ("N", "Einzelschritt (in der Pause)"),
    ("WASD / Pfeile", "Karte bewegen"),
    ("Rechte Maustaste", "Karte ziehen"),
    ("Mausrad", "Zoom (über der Karte)"),
    ("Linksklick", "Minion oder Raubtier auswählen"),
    ("F", "Ausgewähltem folgen"),
    ("Pos1", "Ganze Karte zeigen"),
    ("G", "Farbe: Gene oder Gruppe"),
    ("R", "Neustart"),
    ("1 – 4", "Reiter wechseln"),
)


class HelpPanel(ScrollPanel):
    def render(self, canvas: pygame.Surface, mouse: tuple[int, int] | None) -> int:
        x, y = PAD, PAD
        w = canvas.get_width() - 2 * PAD
        theme.text(canvas, "Tastenkürzel", (x, y), theme.TEXT, 15, bold=True)
        y += 24
        for key, what in SHORTCUTS:
            theme.text(canvas, key, (x, y), theme.TEXT, 13)
            theme.text(canvas, what, (x + 130, y), theme.TEXT_SECONDARY, 13)
            y += 19
        y += 14

        theme.text(canvas, "Minions", (x, y), theme.TEXT, 15, bold=True)
        y += 24
        lines = (
            "Kreis: ein Minion. Größe = Stärke (Jungtiere kleiner),",
            "Farbe = Persönlichkeit (Gene) bzw. Gruppe (Taste G).",
            "Farbiger Ring: Gruppe.  Grüner Balken: Energie.",
        )
        for line in lines:
            theme.text(canvas, line, (x, y), theme.TEXT_SECONDARY, 12)
            y += 17
        pygame.draw.polygon(canvas, CROWN_COLOR, [(x, y + 12), (x, y + 3), (x + 4, y + 7), (x + 7, y + 2),
                                                  (x + 10, y + 7), (x + 14, y + 3), (x + 14, y + 12)])  # fmt: skip
        theme.text(canvas, "Anführer einer Gruppe", (x + 24, y), theme.TEXT_SECONDARY, 12)
        y += 24

        theme.text(canvas, "Punkt oben rechts: aktuelle Aktion", (x, y), theme.TEXT, 13, bold=True)
        y += 20
        col_w = w // 2
        shown = [(a, c) for a, c in ACTION_COLORS.items() if c is not None]
        for i, (action, color) in enumerate(shown):
            cx, cy = x + (i % 2) * col_w, y + (i // 2) * 19
            pygame.draw.circle(canvas, color, (cx + 6, cy + 8), 5)
            theme.text(canvas, action.value, (cx + 18, cy), theme.TEXT_SECONDARY, 12)
        y += ((len(shown) + 1) // 2) * 19
        theme.text(canvas, f"Ohne Punkt: {Action.REST.value}, {Action.WANDER.value}", (x, y), theme.TEXT_MUTED, 12)
        y += 28

        theme.text(canvas, "Raubtiere (Dreiecke)", (x, y), theme.TEXT, 15, bold=True)
        y += 22
        for state in PredatorState:
            pygame.draw.polygon(canvas, PREDATOR_COLORS[state], [(x + 12, y + 8), (x, y + 2), (x, y + 14)])
            theme.text(canvas, state.value, (x + 22, y), theme.TEXT_SECONDARY, 12)
            y += 19
        return y + PAD
