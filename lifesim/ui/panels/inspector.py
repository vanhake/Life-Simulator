"""Inspector tab: everything about the selected minion or predator.

Relatives and acquaintances that are still alive are links: clicking one selects it.
"""

from __future__ import annotations

import pygame

from lifesim.agents.genome import GENE_NAMES, GENE_NAMES_DE
from lifesim.agents.minion import Minion
from lifesim.agents.needs import LEVEL_NAMES_DE, NEED_NAMES_DE
from lifesim.agents.predator import Predator
from lifesim.ui import theme
from lifesim.ui.panels.base import PAD, ScrollPanel

BAR_H = 9
VALUE_W = 60  # room right of a bar for its value text
NEGATIVE = (230, 103, 103)  # diverging pair: red for enmity ...
POSITIVE = theme.SERIES[0]  # ... blue for friendship


class InspectorPanel(ScrollPanel):
    def render(self, canvas: pygame.Surface, mouse: tuple[int, int] | None) -> int:
        sel = self.app.selected
        if isinstance(sel, Minion):
            return self._minion(canvas, sel, mouse)
        if isinstance(sel, Predator):
            return self._predator(canvas, sel, mouse)
        theme.text(canvas, "Nichts ausgewählt.", (PAD, PAD), theme.TEXT, 15, bold=True)
        theme.text(canvas, "Klicke auf der Karte auf einen Minion", (PAD, PAD + 26), theme.TEXT_SECONDARY)
        theme.text(canvas, "oder ein Raubtier.", (PAD, PAD + 44), theme.TEXT_SECONDARY)
        return 100

    # ------------------------------------------------------------------ helpers

    def _button(self, canvas, label: str, pos, mouse, action) -> pygame.Rect:
        img = theme.font(12).render(label, True, theme.TEXT)
        rect = img.get_rect(topleft=pos).inflate(14, 8)
        rect.topleft = pos
        hover = mouse is not None and rect.collidepoint(mouse)
        pygame.draw.rect(canvas, theme.GRID if hover else theme.SURFACE_RAISED, rect, border_radius=4)
        pygame.draw.rect(canvas, theme.GRID, rect, 1, border_radius=4)
        canvas.blit(img, img.get_rect(center=rect.center))
        self.link(rect, action)
        return rect

    def _ref(self, canvas, minion_id: int, pos, mouse, alive: dict[int, Minion]) -> pygame.Rect:
        """A minion id; a link if that minion is alive, marked with † otherwise."""
        other = alive.get(minion_id)
        if other is None:
            return theme.text(canvas, f"#{minion_id}†", pos, theme.TEXT_MUTED, 13)
        rect = theme.text(canvas, f"#{minion_id}", pos, theme.ACCENT, 13)
        if mouse is not None and rect.collidepoint(mouse):
            pygame.draw.line(canvas, theme.ACCENT, rect.bottomleft, rect.bottomright, 1)
        self.link(rect.inflate(4, 4), lambda o=other: self.app.select(o))
        return rect

    def _refs(self, canvas, ids, x, y, w, mouse, alive) -> int:
        """Wrap a list of id links; returns the y below them."""
        cx = x
        if not ids:
            theme.text(canvas, "–", (x, y), theme.TEXT_MUTED, 13)
            return y + 18
        for mid in ids:
            width = theme.font(13).size(f"#{mid}†")[0] + 8
            if cx + width > x + w:
                cx, y = x, y + 18
            self._ref(canvas, mid, (cx, y), mouse, alive)
            cx += width
        return y + 18

    @staticmethod
    def _bar(canvas, x, y, w, frac, color) -> None:
        pygame.draw.rect(canvas, theme.GRID, (x, y, w, BAR_H), border_radius=2)
        pygame.draw.rect(canvas, color, (x, y, max(0, min(1, frac)) * w, BAR_H), border_radius=2)

    def _labelled_bar(self, canvas, x, y, w, label, frac, color, value: str) -> int:
        theme.text(canvas, label, (x, y), theme.TEXT_SECONDARY, 12)
        theme.text(canvas, value, (x + w, y), theme.TEXT, 12, anchor="topright")
        self._bar(canvas, x + 128, y + 4, w - 128 - VALUE_W, frac, color)
        return y + 17

    @staticmethod
    def _heading(canvas, label: str, x: int, y: int) -> int:
        theme.text(canvas, label, (x, y), theme.TEXT, 13, bold=True)
        return y + 20

    # ------------------------------------------------------------------ minion

    def _minion(self, canvas: pygame.Surface, m: Minion, mouse) -> int:
        sim = self.app.sim
        tpd = sim.config.ticks_per_day
        w = canvas.get_width() - 2 * PAD
        x, y = PAD, PAD
        alive = {o.id: o for o in sim.minions}
        rec = sim.lineage[m.id]

        theme.text(canvas, f"Minion #{m.id}", (x, y), theme.TEXT, 17, bold=True)
        status = "lebt" if m.alive else f"tot – {m.death_cause.value}"
        theme.text(canvas, status, (x + w, y + 3), theme.TEXT_SECONDARY, 13, anchor="topright")
        y += 28
        bx = x
        if m.alive:
            follow = "Nicht mehr folgen" if self.app.follow else "Folgen"
            bx = self._button(canvas, follow, (bx, y), mouse, self.app.toggle_follow).right + 8
        self._button(canvas, "Abwählen", (bx, y), mouse, lambda: self.app.select(None))
        y += 34

        group = sim.groups.get(m.group_id)
        if group is not None:
            pygame.draw.circle(canvas, group.color, (x + 6, y + 8), 6, 3)
            r = theme.text(canvas, f"Gruppe #{group.id} ({len(group.members)} Mitglieder), ", (x + 18, y), theme.TEXT, 13)
            if group.leader == m.id:
                theme.text(canvas, "Anführer", (r.right, y), theme.TEXT, 13, bold=True)
            else:
                r2 = theme.text(canvas, "Anführer ", (r.right, y), theme.TEXT, 13)
                self._ref(canvas, group.leader, (r2.right, y), mouse, alive)
        else:
            theme.text(canvas, "Gehört keiner Gruppe an", (x, y), theme.TEXT_SECONDARY, 13)
        y += 20
        theme.text(canvas, f"Aktion: {m.action.value}", (x, y), theme.TEXT, 13)
        y += 24

        y = self._labelled_bar(canvas, x, y, w, "Energie", m.energy_frac, theme.SERIES[0],
                               f"{m.energy:.0f}/{m.traits.max_energy:.0f}")  # fmt: skip
        stage = "" if m.is_adult else " (jung)"
        y = self._labelled_bar(canvas, x, y, w, f"Alter{stage}", m.age / m.max_age, theme.TEXT_MUTED,
                               f"{m.age / tpd:.1f}/{m.max_age / tpd:.0f} T".replace(".", ","))  # fmt: skip
        y += 10

        y = self._heading(canvas, "Bedürfnisse (Maslow)", x, y)
        y = self._pyramid(canvas, x, y, w, m.needs.levels()) + 8
        needs = m.needs
        for key, label in NEED_NAMES_DE.items():
            v = getattr(needs, key)
            y = self._labelled_bar(canvas, x, y, w, label, v, theme.satisfaction_color(v), f"{v:.0%}")
        y += 10

        y = self._heading(canvas, "Gene", x, y)
        for g in GENE_NAMES:
            v = m.genome[g]
            y = self._labelled_bar(canvas, x, y, w, GENE_NAMES_DE[g], v, theme.SERIES[0], f"{v:.2f}".replace(".", ","))
        y += 10

        y = self._heading(canvas, "Familie", x, y)
        theme.text(canvas, f"Generation {m.generation}", (x, y), theme.TEXT_SECONDARY, 13)
        y += 18
        theme.text(canvas, "Eltern:", (x, y), theme.TEXT_SECONDARY, 13)
        if rec.parents:
            y = self._refs(canvas, list(rec.parents), x + 90, y, w - 90, mouse, alive)
        else:
            theme.text(canvas, "Gründer", (x + 90, y), theme.TEXT, 13)
            y += 18
        grand = sim.lineage.ancestors(m.id, 2)
        theme.text(canvas, "Großeltern:", (x, y), theme.TEXT_SECONDARY, 13)
        y = self._refs(canvas, grand[1] if len(grand) > 1 else [], x + 90, y, w - 90, mouse, alive)
        theme.text(canvas, f"Kinder ({len(rec.children)}):", (x, y), theme.TEXT_SECONDARY, 13)
        y = self._refs(canvas, rec.children, x + 90, y, w - 90, mouse, alive)
        theme.text(canvas, f"Nachkommen insgesamt: {sim.lineage.descendant_count(m.id)}", (x, y),
                   theme.TEXT_SECONDARY, 13)  # fmt: skip
        y += 28

        y = self._heading(canvas, "Beziehungen", x, y)
        ties = sim.relations.strongest(m.id, 6)
        if not ties:
            theme.text(canvas, "keine", (x, y), theme.TEXT_MUTED, 13)
            y += 18
        for other, value in ties:
            self._ref(canvas, other, (x, y), mouse, alive)
            kind = "Freund" if value > 0 else "Feind"
            theme.text(canvas, kind, (x + 70, y), theme.TEXT_SECONDARY, 12)
            mid = x + 180
            half = (w - 180 - VALUE_W) / 2
            pygame.draw.line(canvas, theme.GRID, (mid + half, y + 2), (mid + half, y + 12), 1)
            bar_w = abs(value) * half
            bar_x = mid + half if value > 0 else mid + half - bar_w
            pygame.draw.rect(canvas, POSITIVE if value > 0 else NEGATIVE, (bar_x, y + 4, bar_w, BAR_H), border_radius=2)
            theme.text(canvas, f"{value:+.2f}".replace(".", ","), (x + w, y), theme.TEXT, 12, anchor="topright")
            y += 18
        y += 10

        y = self._heading(canvas, "Erfahrung", x, y)
        for label, value in (
            ("Früchte gegessen", f"{m.fruits_eaten}"),
            ("Geschick bei der Futtersuche", f"{m.skill:.0%}"),
            ("Kämpfe gewonnen / verloren", f"{m.fights_won} / {m.fights_lost}"),
            ("Futter geteilt", f"{m.times_shared}"),
            ("Erkundete Gegenden", f"{len(m.explored)}"),
        ):
            theme.text(canvas, label, (x, y), theme.TEXT_SECONDARY, 13)
            theme.text(canvas, value, (x + w, y), theme.TEXT, 13, anchor="topright")
            y += 18
        return y + PAD

    def _pyramid(self, canvas, x: int, y: int, w: int, levels) -> int:
        tier_h, gap, shrink = 18, 2, 38
        for i in reversed(range(len(levels))):
            tw = w - i * shrink
            ty = y + (len(levels) - 1 - i) * (tier_h + gap)
            rect = pygame.Rect(x + (w - tw) // 2, ty, tw, tier_h)
            pygame.draw.rect(canvas, theme.satisfaction_color(levels[i]), rect, border_radius=3)
            label = f"{LEVEL_NAMES_DE[i]} {levels[i]:.0%}"
            theme.text(canvas, label, rect.center, (20, 20, 24), 11, anchor="center")
        return y + len(levels) * (tier_h + gap)

    # ------------------------------------------------------------------ predator

    def _predator(self, canvas: pygame.Surface, p: Predator, mouse) -> int:
        sim = self.app.sim
        tpd = sim.config.ticks_per_day
        w = canvas.get_width() - 2 * PAD
        x, y = PAD, PAD
        theme.text(canvas, f"Raubtier #{p.id}", (x, y), theme.TEXT, 17, bold=True)
        theme.text(canvas, "lebt" if p.alive else "tot", (x + w, y + 3), theme.TEXT_SECONDARY, 13, anchor="topright")
        y += 28
        bx = x
        if p.alive:
            follow = "Nicht mehr folgen" if self.app.follow else "Folgen"
            bx = self._button(canvas, follow, (bx, y), mouse, self.app.toggle_follow).right + 8
        self._button(canvas, "Abwählen", (bx, y), mouse, lambda: self.app.select(None))
        y += 34
        theme.text(canvas, f"Zustand: {p.state.value}", (x, y), theme.TEXT, 13)
        y += 22
        y = self._labelled_bar(canvas, x, y, w, "Energie", p.energy_frac, theme.SERIES[1],
                               f"{p.energy:.0f}/{p.max_energy:.0f}")  # fmt: skip
        y = self._labelled_bar(canvas, x, y, w, "Alter", p.age / p.max_age, theme.TEXT_MUTED,
                               f"{p.age / tpd:.1f}/{p.max_age / tpd:.0f} T".replace(".", ","))  # fmt: skip
        y += 8
        alive = {o.id: o for o in sim.minions}
        theme.text(canvas, "Beute:", (x, y), theme.TEXT_SECONDARY, 13)
        if p.prey is not None and p.prey.alive:
            self._ref(canvas, p.prey.id, (x + 90, y), mouse, alive)
        else:
            theme.text(canvas, "–", (x + 90, y), theme.TEXT_MUTED, 13)
        y += 18
        for label, value in (
            ("Minions gefressen", f"{p.kills}"),
            ("Nachwuchs möglich in", f"{p.breed_cooldown / tpd:.1f} Tagen".replace(".", ",")),
        ):
            theme.text(canvas, label, (x, y), theme.TEXT_SECONDARY, 13)
            theme.text(canvas, value, (x + w, y), theme.TEXT, 13, anchor="topright")
            y += 18
        return y + PAD
