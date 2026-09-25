"""Genome: a fixed list of genes, each a float in [0, 1]."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

BODY_GENES = (
    "speed",
    "strength",
    "max_energy",
    "metabolism",
    "vision",
    "lifespan",
    "fertility",
    "activity_need",
)
PERSONALITY_GENES = (
    "aggression",
    "sociability",
    "altruism",
    "curiosity",
    "fearfulness",
)
GENE_NAMES = BODY_GENES + PERSONALITY_GENES

GENE_NAMES_DE = {
    "speed": "Geschwindigkeit",
    "strength": "Stärke",
    "max_energy": "Energiespeicher",
    "metabolism": "Stoffwechsel",
    "vision": "Sichtweite",
    "lifespan": "Lebensspanne",
    "fertility": "Fruchtbarkeit",
    "activity_need": "Bewegungsbedarf",
    "aggression": "Aggression",
    "sociability": "Geselligkeit",
    "altruism": "Altruismus",
    "curiosity": "Neugier",
    "fearfulness": "Ängstlichkeit",
}


def _clamp01(v: float) -> float:
    return 0.0 if v < 0.0 else 1.0 if v > 1.0 else v


@dataclass
class Genome:
    genes: dict[str, float] = field(default_factory=dict)

    def __getitem__(self, name: str) -> float:
        return self.genes[name]

    @classmethod
    def random(cls, rng: random.Random, spread: float = 0.15) -> "Genome":
        """Random genome clustered around the midpoint, so the founders are varied but viable."""
        return cls({n: _clamp01(rng.gauss(0.5, spread)) for n in GENE_NAMES})

    @classmethod
    def crossover(cls, a: "Genome", b: "Genome", rng: random.Random) -> "Genome":
        return cls({n: (a[n] if rng.random() < 0.5 else b[n]) for n in GENE_NAMES})

    def mutated(self, rng: random.Random, rate: float, strength: float) -> "Genome":
        return Genome(
            {
                n: _clamp01(v + rng.gauss(0.0, strength)) if rng.random() < rate else v
                for n, v in self.genes.items()
            }
        )

    def distance(self, other: "Genome") -> float:
        """Mean absolute gene difference, in [0, 1]."""
        return sum(abs(self[n] - other[n]) for n in GENE_NAMES) / len(GENE_NAMES)
