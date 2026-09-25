"""Fractal value noise implemented with numpy (no extra dependency)."""

from __future__ import annotations

import numpy as np


def _smooth(t: np.ndarray) -> np.ndarray:
    return t * t * (3.0 - 2.0 * t)


def value_noise(width: int, height: int, scale: float, rng: np.random.Generator) -> np.ndarray:
    """Single octave of smoothly interpolated value noise in [0, 1]."""
    gw = int(np.ceil(width / scale)) + 2
    gh = int(np.ceil(height / scale)) + 2
    grid = rng.random((gh, gw))

    ys = np.arange(height) / scale
    xs = np.arange(width) / scale
    y0 = ys.astype(int)
    x0 = xs.astype(int)
    ty = _smooth(ys - y0)[:, None]
    tx = _smooth(xs - x0)[None, :]

    v00 = grid[y0[:, None], x0[None, :]]
    v10 = grid[y0[:, None], x0[None, :] + 1]
    v01 = grid[y0[:, None] + 1, x0[None, :]]
    v11 = grid[y0[:, None] + 1, x0[None, :] + 1]
    top = v00 + (v10 - v00) * tx
    bottom = v01 + (v11 - v01) * tx
    return top + (bottom - top) * ty


def fractal_noise(
    width: int,
    height: int,
    rng: np.random.Generator,
    base_scale: float = 24.0,
    octaves: int = 4,
    persistence: float = 0.5,
) -> np.ndarray:
    """Sum of octaves, normalised to [0, 1]. Returned array has shape (height, width)."""
    total = np.zeros((height, width))
    amplitude = 1.0
    scale = base_scale
    for _ in range(octaves):
        total += amplitude * value_noise(width, height, max(scale, 1.0), rng)
        amplitude *= persistence
        scale /= 2.0
    lo, hi = total.min(), total.max()
    if hi - lo < 1e-9:
        return np.zeros_like(total)
    return (total - lo) / (hi - lo)
