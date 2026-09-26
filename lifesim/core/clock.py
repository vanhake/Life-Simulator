"""Time of day and seasons derived from the tick counter."""

from __future__ import annotations

import math

SEASON_NAMES_DE = ("Frühling", "Sommer", "Herbst", "Winter")
# How fast fruit regrows relative to the base rate.
SEASON_FRUIT_FACTOR = (1.0, 1.4, 0.9, 0.35)
# How likely trees are to spread seeds relative to the base rate.
SEASON_SEED_FACTOR = (1.5, 1.0, 0.4, 0.0)

NIGHT_THRESHOLD = 0.3


class Clock:
    def __init__(self, ticks_per_day: int, days_per_season: int) -> None:
        self.ticks_per_day = max(1, ticks_per_day)
        self.days_per_season = max(1, days_per_season)
        self.tick = 0

    @property
    def day(self) -> int:
        return self.tick // self.ticks_per_day

    @property
    def time_of_day(self) -> float:
        """0.0 = midnight, 0.5 = noon."""
        return (self.tick % self.ticks_per_day) / self.ticks_per_day

    @property
    def daylight(self) -> float:
        """Brightness in [0, 1]: 0 around midnight, 1 around noon, with short twilights."""
        sun = -math.cos(self.time_of_day * 2 * math.pi)  # -1 midnight .. 1 noon
        return min(1.0, max(0.0, sun * 1.5 + 0.5))

    @property
    def is_night(self) -> bool:
        return self.daylight < NIGHT_THRESHOLD

    @property
    def season(self) -> int:
        return (self.day // self.days_per_season) % 4

    @property
    def season_name(self) -> str:
        return SEASON_NAMES_DE[self.season]

    @property
    def year(self) -> int:
        return self.day // (self.days_per_season * 4)

    @property
    def fruit_factor(self) -> float:
        return SEASON_FRUIT_FACTOR[self.season]

    @property
    def seed_factor(self) -> float:
        return SEASON_SEED_FACTOR[self.season]

    def clock_text(self) -> str:
        minutes = int(self.time_of_day * 24 * 60)
        return f"{minutes // 60:02d}:{minutes % 60:02d}"
