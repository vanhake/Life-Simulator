"""Emergent groups: communities of strong friendship, with a leader and stable ids.

Groups are found by label propagation: every minion repeatedly adopts the group its
friends are most strongly tied to. Starting from the previous grouping keeps group
identities stable, and unlike plain "friend of a friend" chaining it does not merge a
dense population into one giant group.
"""

from __future__ import annotations

import colorsys
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from lifesim.social.relations import Relations

if TYPE_CHECKING:
    from lifesim.agents.minion import Minion

MIN_GROUP_SIZE = 3
GROUP_BOND = 0.4  # relation needed for a tie that counts towards group membership
PROPAGATION_ROUNDS = 8
INERTIA = 0.3  # bonus for keeping one's current group, damps oscillation
GOLDEN_RATIO = 0.618033988749895


@dataclass
class Group:
    id: int
    members: set[int] = field(default_factory=set)
    leader: int | None = None
    founded: int = 0  # tick

    @property
    def color(self) -> tuple[int, int, int]:
        hue = (self.id * GOLDEN_RATIO) % 1.0
        r, g, b = colorsys.hsv_to_rgb(hue, 0.85, 1.0)
        return int(r * 255), int(g * 255), int(b * 255)


class Groups:
    def __init__(self) -> None:
        self.groups: dict[int, Group] = {}
        self._next_id = 1

    def __len__(self) -> int:
        return len(self.groups)

    def get(self, group_id: int | None) -> Group | None:
        return self.groups.get(group_id) if group_id is not None else None

    def update(
        self, minions: list["Minion"], relations: Relations, tick: int, rng: random.Random
    ) -> None:
        """Re-detect communities, keeping ids of groups that persist."""
        by_id = {m.id: m for m in minions}
        communities = self._communities(by_id, relations, rng)

        old = self.groups
        new: dict[int, Group] = {}
        for label, members in sorted(communities, key=lambda c: (-len(c[1]), str(c[0]))):
            if isinstance(label, int) and label in old and label not in new:
                group = old[label]
            else:
                group = Group(self._next_id, founded=tick)
                self._next_id += 1
            group.members = members
            group.leader = max(members, key=lambda i: (by_id[i].needs.status, -i))
            new[group.id] = group
        self.groups = new

        for m in minions:
            m.group_id = None
        for g in new.values():
            for mid in g.members:
                by_id[mid].group_id = g.id

    @staticmethod
    def _communities(
        by_id: dict[int, "Minion"], relations: Relations, rng: random.Random
    ) -> list[tuple[object, set[int]]]:
        ties: dict[int, list[tuple[int, float]]] = {
            a: [(b, v) for b, v in relations.of(a).items() if v >= GROUP_BOND and b in by_id]
            for a in by_id
        }
        # Start from the current groups; loners start with a label of their own.
        labels: dict[int, object] = {
            a: (m.group_id if m.group_id is not None else ("solo", a)) for a, m in by_id.items()
        }
        order = sorted(a for a in by_id if ties[a])
        for _ in range(PROPAGATION_ROUNDS):
            rng.shuffle(order)
            changed = False
            for a in order:
                weight: dict[object, float] = {labels[a]: INERTIA}
                for b, v in ties[a]:
                    weight[labels[b]] = weight.get(labels[b], 0.0) + v
                best = max(weight, key=lambda lbl: (weight[lbl], lbl == labels[a]))
                if best != labels[a]:
                    labels[a] = best
                    changed = True
            if not changed:
                break

        # A label may cover disconnected parts; each connected part is its own community,
        # the largest part keeps the label.
        by_label: dict[object, set[int]] = {}
        for a, lbl in labels.items():
            by_label.setdefault(lbl, set()).add(a)
        result: list[tuple[object, set[int]]] = []
        for lbl, members in by_label.items():
            parts = []
            unvisited = set(members)
            while unvisited:
                start = unvisited.pop()
                part, stack = {start}, [start]
                while stack:
                    a = stack.pop()
                    for b, _ in ties[a]:
                        if b in unvisited:
                            unvisited.discard(b)
                            part.add(b)
                            stack.append(b)
                parts.append(part)
            parts.sort(key=len, reverse=True)
            for i, part in enumerate(parts):
                if len(part) >= MIN_GROUP_SIZE:
                    result.append((lbl if i == 0 else ("split", min(part)), part))
        return result
