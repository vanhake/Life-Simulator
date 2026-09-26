"""Maslow's hierarchy of needs as simulated values.

Every need has a satisfaction in [0, 1]. Higher levels only become motivating once the
levels below are reasonably satisfied (soft gating), mirroring Maslow's pyramid.
"""

from __future__ import annotations

from dataclasses import dataclass


def clamp01(v: float) -> float:
    return 0.0 if v < 0.0 else 1.0 if v > 1.0 else v


def smoothstep(lo: float, hi: float, v: float) -> float:
    """0 at `lo`, 1 at `hi`, smooth in between (`lo` may be greater than `hi`)."""
    t = clamp01((v - lo) / (hi - lo))
    return t * t * (3 - 2 * t)


LEVEL_NAMES_DE = (
    "Physiologie",
    "Sicherheit",
    "Soziales",
    "Anerkennung",
    "Selbstverwirklichung",
)

NEED_NAMES_DE = {
    "hunger": "Sättigung",
    "rest": "Ausgeruht",
    "activity": "Bewegung",
    "safety": "Sicherheit",
    "belonging": "Zugehörigkeit",
    "partner": "Partnerschaft",
    "status": "Anerkennung",
    "fulfilment": "Erfüllung",
}


@dataclass
class Needs:
    # Level 1 – physiological. Hunger satisfaction is the energy fraction, kept in sync.
    hunger: float = 1.0
    rest: float = 1.0
    activity: float = 1.0
    # Level 2 – safety
    safety: float = 1.0
    # Level 3 – love and belonging
    belonging: float = 0.5
    partner: float = 1.0  # drops while the minion is ready to mate but has not
    # Level 4 – esteem
    status: float = 0.0
    # Level 5 – self-actualisation (novel experiences and growing skill)
    fulfilment: float = 0.5

    def levels(self) -> tuple[float, float, float, float, float]:
        """Satisfaction per pyramid level, bottom to top."""
        return (
            min(self.hunger, self.rest, self.activity),
            self.safety,
            (self.belonging + self.partner) / 2,
            self.status,
            self.fulfilment,
        )

    def gate(self, level: int) -> float:
        """How strongly needs on `level` (1..5) may motivate, given the levels below.

        Deficiency needs (levels 1–3) gate hard; esteem gates only partially so that
        self-actualisation still happens for minions without high status.
        """
        lv = self.levels()
        g = 1.0
        for i in range(level - 1):
            if i < 3:
                g *= smoothstep(0.15, 0.55, lv[i])
            else:
                g *= 0.5 + 0.5 * lv[i]
        return g
