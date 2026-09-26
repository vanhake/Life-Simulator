"""Family-tree records that outlive the minions they describe."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LineageRecord:
    id: int
    parents: tuple[int, int] | None
    generation: int
    born: int  # tick
    died: int | None = None  # tick
    cause: str | None = None
    children: list[int] = field(default_factory=list)


class Lineage:
    def __init__(self) -> None:
        self.records: dict[int, LineageRecord] = {}

    def __getitem__(self, minion_id: int) -> LineageRecord:
        return self.records[minion_id]

    def get(self, minion_id: int) -> LineageRecord | None:
        return self.records.get(minion_id)

    def birth(
        self, minion_id: int, parents: tuple[int, int] | None, generation: int, tick: int
    ) -> None:
        self.records[minion_id] = LineageRecord(minion_id, parents, generation, tick)
        if parents:
            for p in parents:
                if p in self.records:
                    self.records[p].children.append(minion_id)

    def death(self, minion_id: int, tick: int, cause: str) -> None:
        rec = self.records[minion_id]
        rec.died = tick
        rec.cause = cause

    def ancestors(self, minion_id: int, depth: int) -> list[list[int]]:
        """Ancestor ids per generation back: [[parents], [grandparents], ...]."""
        levels: list[list[int]] = []
        current = [minion_id]
        for _ in range(depth):
            nxt = [p for mid in current if (r := self.get(mid)) and r.parents for p in r.parents]
            if not nxt:
                break
            levels.append(nxt)
            current = nxt
        return levels

    def descendant_count(self, minion_id: int) -> int:
        seen: set[int] = set()
        stack = list(self.records[minion_id].children)
        while stack:
            cid = stack.pop()
            if cid in seen:
                continue
            seen.add(cid)
            stack.extend(self.records[cid].children)
        return len(seen)
