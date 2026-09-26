"""Symmetric relationship values between minions, in [-1, 1].

Positive values mean sympathy (time spent together, shared food, kinship), negative
values mean enmity (fights). Values fade towards zero unless they are renewed.
"""

from __future__ import annotations

FRIEND_THRESHOLD = 0.3
FORGET_BELOW = 0.02


class Relations:
    def __init__(self) -> None:
        self._rel: dict[int, dict[int, float]] = {}

    def get(self, a: int, b: int) -> float:
        row = self._rel.get(a)
        return row.get(b, 0.0) if row else 0.0

    def set(self, a: int, b: int, value: float) -> None:
        if a == b:
            return
        value = max(-1.0, min(1.0, value))
        self._rel.setdefault(a, {})[b] = value
        self._rel.setdefault(b, {})[a] = value

    def add(self, a: int, b: int, delta: float) -> float:
        value = self.get(a, b) + delta
        self.set(a, b, value)
        return value

    def is_friend(self, a: int, b: int) -> bool:
        return self.get(a, b) >= FRIEND_THRESHOLD

    def of(self, a: int) -> dict[int, float]:
        return self._rel.get(a, {})

    def strongest(self, a: int, n: int = 3) -> list[tuple[int, float]]:
        """The `n` relations with the largest magnitude."""
        return sorted(self.of(a).items(), key=lambda kv: -abs(kv[1]))[:n]

    def remove(self, a: int) -> None:
        for b in self._rel.pop(a, {}):
            row = self._rel.get(b)
            if row is not None:
                row.pop(a, None)

    def decay(self, factor: float) -> None:
        """Multiply every value by `factor` and forget the ones that became negligible."""
        for a, row in list(self._rel.items()):
            for b in list(row):
                v = row[b] * factor
                if abs(v) < FORGET_BELOW:
                    del row[b]
                else:
                    row[b] = v
            if not row:
                del self._rel[a]

    def pairs(self) -> int:
        return sum(len(row) for row in self._rel.values()) // 2
