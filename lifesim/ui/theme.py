"""Colours and fonts shared by the side panel and the charts (dark UI).

Series colours are the first slots of a colour-blind-validated categorical palette,
stepped for a dark surface, and always assigned in this fixed order.
"""

from __future__ import annotations

import pygame

SURFACE = (26, 26, 25)  # panel and chart background
SURFACE_RAISED = (38, 38, 36)
GRID = (56, 56, 53)
TEXT = (255, 255, 255)
TEXT_SECONDARY = (195, 194, 183)
TEXT_MUTED = (140, 139, 131)
ACCENT = (57, 135, 229)

SERIES = (
    (57, 135, 229),  # 1 blue    – minions
    (217, 89, 38),  # 2 orange  – predators
    (25, 158, 112),  # 3 aqua    – groups
)

# Satisfaction / status scale: critical -> warning -> good. Always shown with a label.
STATUS_CRITICAL = (208, 59, 59)
STATUS_WARNING = (250, 178, 25)
STATUS_GOOD = (12, 163, 12)


def satisfaction_color(v: float) -> tuple[int, int, int]:
    """Critical (unsatisfied) through warning to good (satisfied)."""
    a, b, t = (
        (STATUS_CRITICAL, STATUS_WARNING, v * 2)
        if v < 0.5
        else (STATUS_WARNING, STATUS_GOOD, (v - 0.5) * 2)
    )
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


_fonts: dict[tuple[int, bool], pygame.font.Font] = {}


def reset_fonts() -> None:
    """Forget cached fonts; they become invalid when pygame is shut down."""
    _fonts.clear()


def font(size: int = 14, bold: bool = False) -> pygame.font.Font:
    if not pygame.font.get_init():
        pygame.font.init()
        _fonts.clear()
    key = (size, bold)
    if key not in _fonts:
        _fonts[key] = pygame.font.SysFont("dejavusans,arial", size, bold=bold)
    return _fonts[key]


def text(
    surface: pygame.Surface,
    content: str,
    pos: tuple[float, float],
    color: tuple[int, int, int] = TEXT,
    size: int = 14,
    bold: bool = False,
    anchor: str = "topleft",
) -> pygame.Rect:
    img = font(size, bold).render(content, True, color)
    rect = img.get_rect(**{anchor: (round(pos[0]), round(pos[1]))})
    surface.blit(img, rect)
    return rect
