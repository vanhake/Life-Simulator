"""Small line charts drawn directly with pygame: one measure per chart, one y-axis.

Each chart shows a title, a recessive grid, the current value as a direct label and,
while the mouse hovers over it, a crosshair with the value at that point in time.
"""

from __future__ import annotations

from collections.abc import Sequence

import pygame

from lifesim.ui import theme

LINE_WIDTH = 2


def _nice_max(v: float) -> float:
    """Round an axis maximum up to 1, 2, 2.5 or 5 times a power of ten."""
    if v <= 0:
        return 1.0
    exp = 10 ** int(f"{v:e}".split("e")[1])
    for m in (1, 2, 2.5, 5, 10):
        if v <= m * exp:
            return m * exp
    return 10 * exp


def _downsample(values: Sequence[float], n: int) -> list[float]:
    if len(values) <= n:
        return list(values)
    step = len(values) / n
    out = [values[int(i * step)] for i in range(n - 1)]
    out.append(values[-1])
    return out


def _fmt(v: float, decimals: int) -> str:
    return f"{v:.{decimals}f}".replace(".", ",")


def line_chart(
    surface: pygame.Surface,
    rect: pygame.Rect,
    title: str,
    values: Sequence[float],
    days: Sequence[float],
    color: tuple[int, int, int],
    mouse: tuple[int, int] | None,
    y_max: float | None = None,
    decimals: int = 0,
) -> None:
    """A single-series chart. `days` gives the x position (in days) of every value."""
    theme.text(surface, title, (rect.x, rect.y), theme.TEXT, 13, bold=True)
    plot = pygame.Rect(rect.x + 34, rect.y + 20, rect.w - 40, rect.h - 36)
    if not values:
        return
    top = y_max if y_max is not None else _nice_max(max(values) * 1.05)

    for i in range(3):  # gridlines at 0, 50 % and 100 %
        gy = plot.bottom - plot.h * i / 2
        pygame.draw.line(surface, theme.GRID, (plot.x, gy), (plot.right, gy), 1)
        theme.text(surface, _fmt(top * i / 2, decimals), (plot.x - 4, gy), theme.TEXT_MUTED, 11,
                   anchor="midright")  # fmt: skip
    theme.text(surface, f"Tag {days[0]:.0f}", (plot.x, plot.bottom + 2), theme.TEXT_MUTED, 11)
    theme.text(surface, f"Tag {days[-1]:.0f}", (plot.right, plot.bottom + 2), theme.TEXT_MUTED, 11,
               anchor="topright")  # fmt: skip

    pts_v = _downsample(values, plot.w)
    pts_d = _downsample(days, plot.w)
    n = len(pts_v)

    def point(i: int) -> tuple[float, float]:
        x = plot.x + (plot.w * i / (n - 1) if n > 1 else plot.w)
        y = plot.bottom - plot.h * min(pts_v[i], top) / top
        return x, y

    if n > 1:
        pygame.draw.lines(surface, color, False, [point(i) for i in range(n)], LINE_WIDTH)
    ex, ey = point(n - 1)
    pygame.draw.circle(surface, color, (ex, ey), 3)
    theme.text(surface, _fmt(pts_v[-1], decimals), (rect.right, rect.y), theme.TEXT, 13,
               anchor="topright")  # fmt: skip

    if mouse is not None and plot.collidepoint(mouse) and n > 1:
        i = round((mouse[0] - plot.x) / plot.w * (n - 1))
        i = max(0, min(n - 1, i))
        hx, hy = point(i)
        pygame.draw.line(surface, theme.TEXT_MUTED, (hx, plot.y), (hx, plot.bottom), 1)
        pygame.draw.circle(surface, theme.SURFACE, (hx, hy), 6)
        pygame.draw.circle(surface, color, (hx, hy), 4)
        tooltip(surface, f"Tag {pts_d[i]:.1f}: {_fmt(pts_v[i], decimals)}", (hx, plot.y), plot)


def sparkline(
    surface: pygame.Surface,
    rect: pygame.Rect,
    label: str,
    values: Sequence[float],
    color: tuple[int, int, int],
    mouse: tuple[int, int] | None,
) -> None:
    """A compact 0..1 trend line with its label and current value (for gene means)."""
    theme.text(surface, label, (rect.x, rect.y), theme.TEXT_SECONDARY, 11)
    plot = pygame.Rect(rect.x, rect.y + 15, rect.w, rect.h - 17)
    mid = plot.bottom - plot.h / 2
    pygame.draw.line(surface, theme.GRID, (plot.x, mid), (plot.right, mid), 1)
    pygame.draw.line(surface, theme.GRID, (plot.x, plot.bottom), (plot.right, plot.bottom), 1)
    if not values:
        return
    pts = _downsample(values, max(2, plot.w // 2))
    n = len(pts)

    def point(i: int) -> tuple[float, float]:
        return plot.x + (plot.w * i / (n - 1) if n > 1 else plot.w), plot.bottom - plot.h * pts[i]

    if n > 1:
        pygame.draw.lines(surface, color, False, [point(i) for i in range(n)], LINE_WIDTH)
    shown = pts[-1]
    if mouse is not None and plot.collidepoint(mouse) and n > 1:
        i = max(0, min(n - 1, round((mouse[0] - plot.x) / plot.w * (n - 1))))
        hx, hy = point(i)
        pygame.draw.line(surface, theme.TEXT_MUTED, (hx, plot.y), (hx, plot.bottom), 1)
        pygame.draw.circle(surface, color, (hx, hy), 3)
        shown = pts[i]
    theme.text(surface, _fmt(shown, 2), (rect.right, rect.y), theme.TEXT, 11, anchor="topright")


def tooltip(
    surface: pygame.Surface, content: str, anchor: tuple[float, float], bounds: pygame.Rect
) -> None:
    img = theme.font(12).render(content, True, theme.TEXT)
    box = img.get_rect().inflate(10, 6)
    box.midbottom = (round(anchor[0]), round(anchor[1]) - 2)
    box.clamp_ip(bounds.inflate(40, 40))
    pygame.draw.rect(surface, theme.SURFACE_RAISED, box, border_radius=4)
    pygame.draw.rect(surface, theme.GRID, box, 1, border_radius=4)
    surface.blit(img, img.get_rect(center=box.center))
