"""World <-> screen transform with zoom and pan."""

from __future__ import annotations


class Camera:
    MIN_ZOOM = 3.0
    MAX_ZOOM = 64.0

    def __init__(self, view_w: int, view_h: int, world_w: int, world_h: int) -> None:
        self.view_w, self.view_h = view_w, view_h
        self.world_w, self.world_h = world_w, world_h
        self.zoom = 1.0  # pixels per tile
        self.x = self.y = 0.0  # world coordinate of the view's top-left corner
        self.fit()

    def fit(self) -> None:
        self.zoom = max(self.MIN_ZOOM, min(self.view_w / self.world_w, self.view_h / self.world_h))
        self.center_on(self.world_w / 2, self.world_h / 2)

    def resize(self, view_w: int, view_h: int) -> None:
        cx, cy = self.screen_to_world(self.view_w / 2, self.view_h / 2)
        self.view_w, self.view_h = view_w, view_h
        self.center_on(cx, cy)

    def center_on(self, wx: float, wy: float) -> None:
        self.x = wx - self.view_w / (2 * self.zoom)
        self.y = wy - self.view_h / (2 * self.zoom)
        self._clamp()

    def pan(self, dx_px: float, dy_px: float) -> None:
        self.x += dx_px / self.zoom
        self.y += dy_px / self.zoom
        self._clamp()

    def zoom_at(self, factor: float, sx: float, sy: float) -> None:
        wx, wy = self.screen_to_world(sx, sy)
        self.zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, self.zoom * factor))
        self.x = wx - sx / self.zoom
        self.y = wy - sy / self.zoom
        self._clamp()

    def _clamp(self) -> None:
        # Keep the map filling the view; centre it on an axis where it is smaller than the view.
        vis_w, vis_h = self.view_w / self.zoom, self.view_h / self.zoom
        self.x = self._clamp_axis(self.x, vis_w, self.world_w)
        self.y = self._clamp_axis(self.y, vis_h, self.world_h)

    @staticmethod
    def _clamp_axis(pos: float, visible: float, world: float) -> float:
        if visible >= world:
            return (world - visible) / 2
        return min(max(pos, 0.0), world - visible)

    def world_to_screen(self, wx: float, wy: float) -> tuple[float, float]:
        return (wx - self.x) * self.zoom, (wy - self.y) * self.zoom

    def screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        return sx / self.zoom + self.x, sy / self.zoom + self.y

    def visible_rect(self) -> tuple[float, float, float, float]:
        return self.x, self.y, self.view_w / self.zoom, self.view_h / self.zoom
