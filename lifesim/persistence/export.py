"""CSV export of the statistics history and of the living minions.

Files use a semicolon separator and a decimal comma so that German Excel opens them
directly. In Python: pandas.read_csv(path, sep=";", decimal=",").
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from lifesim.agents.genome import GENE_NAMES
from lifesim.agents.needs import NEED_NAMES_DE
from lifesim.core.simulation import Simulation

EXPORT_DIR = Path("exports")


def _cell(value) -> str:
    if isinstance(value, float):
        return f"{value:.6g}".replace(".", ",")
    return str(value)


def _write(path: Path, header: list[str], rows: list[list]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:  # BOM: Excel detects UTF-8
        writer = csv.writer(f, delimiter=";")
        writer.writerow(header)
        writer.writerows([_cell(v) for v in row] for row in rows)
    return path


def export_history(sim: Simulation, path: Path | str) -> Path:
    """One row per statistics sample (every 30 ticks): population, deaths, gene means …"""
    history = sim.history
    header = list(history[0].keys()) if history else []
    header.insert(1, "tag_dezimal")
    tpd = sim.config.ticks_per_day
    rows = []
    for row in history:
        values = list(row.values())
        values.insert(1, row["tick"] / tpd)
        rows.append(values)
    return _write(Path(path), header, rows)


def export_minions(sim: Simulation, path: Path | str) -> Path:
    """One row per living minion: identity, family, state, needs and genes."""
    tpd = sim.config.ticks_per_day
    header = [
        "id", "generation", "eltern", "gruppe", "anfuehrer", "alter_tage", "energie",
        "aktion", "x", "y", "kinder", "fruechte", "kaempfe_gewonnen", "kaempfe_verloren",
        "geteilt", *(f"beduerfnis_{k}" for k in NEED_NAMES_DE), *(f"gen_{g}" for g in GENE_NAMES),
    ]  # fmt: skip
    rows = []
    for m in sim.minions:
        group = sim.groups.get(m.group_id)
        rows.append([
            m.id, m.generation, "-".join(map(str, m.parents)) if m.parents else "",
            m.group_id if m.group_id is not None else "",
            int(group is not None and group.leader == m.id),
            m.age / tpd, m.energy, m.action.value, m.x, m.y, m.children, m.fruits_eaten,
            m.fights_won, m.fights_lost, m.times_shared,
            *(float(getattr(m.needs, k)) for k in NEED_NAMES_DE), *(m.genome[g] for g in GENE_NAMES),
        ])  # fmt: skip
    return _write(Path(path), header, rows)


def export_all(sim: Simulation, directory: Path = EXPORT_DIR) -> tuple[Path, Path]:
    stamp = f"{datetime.now():%Y-%m-%d_%H-%M-%S}"
    return (
        export_history(sim, directory / f"verlauf_{stamp}.csv"),
        export_minions(sim, directory / f"minions_{stamp}.csv"),
    )
