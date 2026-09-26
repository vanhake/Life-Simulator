"""Base for side-panel tabs that draw their own content and scroll with the mouse wheel."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import pygame

from lifesim.ui import theme

if TYPE_CHECKING:
    from lifesim.ui.app import App

SCROLL_STEP = 40
PAD = 12


class ScrollPanel:
    """Draws onto a tall off-screen canvas and shows the scrolled part of it.

    Subclasses implement `render(canvas, mouse) -> content height`; `mouse` is given in
    canvas coordinates (or None when the pointer is elsewhere). Clickable areas are
    registered during rendering with `link()`.
    """

    def __init__(self, app: "App") -> None:
        self.app = app
        self.scroll = 0
        self._content_h = 0
        self._links: list[tuple[pygame.Rect, Callable[[], None]]] = []

    def render(self, canvas: pygame.Surface, mouse: tuple[int, int] | None) -> int:
        raise NotImplementedError

    def link(self, rect: pygame.Rect, action: Callable[[], None]) -> None:
        self._links.append((rect, action))

    def draw(self, screen: pygame.Surface, rect: pygame.Rect, mouse: tuple[int, int]) -> None:
        canvas = pygame.Surface((rect.w, max(rect.h, self._content_h)))
        canvas.fill(theme.SURFACE)
        local = (mouse[0] - rect.x, mouse[1] - rect.y + self.scroll) if rect.collidepoint(mouse) else None
        self._links = []
        self._content_h = self.render(canvas, local)
        self.scroll = max(0, min(self.scroll, self._content_h - rect.h))
        screen.blit(canvas, rect.topleft, pygame.Rect(0, self.scroll, rect.w, rect.h))
        if self._content_h > rect.h:  # scroll indicator
            bar_h = max(20, rect.h * rect.h // self._content_h)
            bar_y = rect.y + (rect.h - bar_h) * self.scroll // max(1, self._content_h - rect.h)
            pygame.draw.rect(screen, theme.GRID, (rect.right - 4, bar_y, 3, bar_h), border_radius=2)

    def click(self, rect: pygame.Rect, pos: tuple[int, int]) -> bool:
        local = (pos[0] - rect.x, pos[1] - rect.y + self.scroll)
        for area, action in self._links:
            if area.collidepoint(local):
                action()
                return True
        return False

    def wheel(self, dy: int) -> None:
        self.scroll = max(0, self.scroll - dy * SCROLL_STEP)
