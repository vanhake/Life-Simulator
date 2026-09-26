import csv
import gzip
import json
import os
import pickle
from pathlib import Path

import pytest

from lifesim import presets
from lifesim.__main__ import main
from lifesim.agents.genome import GENE_NAMES
from lifesim.config import SimConfig
from lifesim.core.simulation import Simulation
from lifesim.persistence import export
from lifesim.persistence import save as savefile


def small_sim(**overrides) -> Simulation:
    cfg = SimConfig(seed=17, map_width=50, map_height=40, initial_minions=40, initial_predators=3)
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return Simulation(cfg)


def state(sim: Simulation) -> tuple:
    return (
        sim.tick,
        [(m.id, round(m.x, 9), round(m.y, 9), round(m.energy, 9), m.group_id) for m in sim.minions],
        [(p.id, round(p.x, 9), round(p.y, 9)) for p in sim.predators],
        sim.births,
        sim.kills,
        len(sim.forest.trees),
    )


# ---------------------------------------------------------------- save / load


def test_loaded_simulation_continues_exactly_like_the_original(tmp_path):
    sim = small_sim()
    for _ in range(3000):
        sim.step()
    path = savefile.save(sim, tmp_path / "a.lifesim")
    loaded = savefile.load(path)
    assert state(loaded) == state(sim)
    for _ in range(2000):
        sim.step()
        loaded.step()
    assert state(loaded) == state(sim)


def test_save_creates_folders_and_lists_newest_first(tmp_path):
    sim = small_sim()
    first = savefile.save(sim, tmp_path / "sub" / "eins.lifesim")
    second = savefile.save(sim, tmp_path / "sub" / "zwei.lifesim")
    os.utime(first, (1, 1))  # make "eins" clearly older
    assert savefile.list_saves(tmp_path / "sub") == [second, first]
    assert savefile.list_saves(tmp_path / "fehlt") == []
    assert not list((tmp_path / "sub").glob("*.tmp"))


def test_loading_garbage_or_foreign_files_fails_cleanly(tmp_path):
    bad = tmp_path / "bad.lifesim"
    bad.write_text("kein Spielstand")
    with pytest.raises(savefile.SaveError):
        savefile.load(bad)
    foreign = tmp_path / "foreign.lifesim"
    with gzip.open(foreign, "wb") as f:
        pickle.dump({"format": "etwas anderes"}, f)
    with pytest.raises(savefile.SaveError):
        savefile.load(foreign)
    with pytest.raises(savefile.SaveError):
        savefile.load(tmp_path / "gibt_es_nicht.lifesim")


# ---------------------------------------------------------------- CSV export


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.reader(f, delimiter=";"))


def test_history_export_is_excel_friendly(tmp_path):
    sim = small_sim()
    for _ in range(300):
        sim.step()
    rows = read_csv(export.export_history(sim, tmp_path / "verlauf.csv"))
    header, data = rows[0], rows[1:]
    assert header[:2] == ["tick", "tag_dezimal"]
    assert "population" in header and f"gene_{GENE_NAMES[0]}" in header
    assert len(data) == len(sim.history)
    col = header.index("tag_dezimal")
    assert "," in data[-1][col] and "." not in data[-1][col]  # decimal comma


def test_minion_export_has_one_row_per_living_minion(tmp_path):
    sim = small_sim()
    for _ in range(600):
        sim.step()
    rows = read_csv(export.export_minions(sim, tmp_path / "minions.csv"))
    header, data = rows[0], rows[1:]
    assert len(data) == len(sim.minions)
    assert {"id", "generation", "gruppe", "aktion"} <= set(header)
    assert all(f"gen_{g}" in header for g in GENE_NAMES)
    ids = {int(r[header.index("id")]) for r in data}
    assert ids == {m.id for m in sim.minions}


# ---------------------------------------------------------------- presets


def test_builtin_presets_are_valid_and_run():
    listed = presets.list_presets(user_dir=Path("/nonexistent"))
    names = [p.name for p in listed]
    assert names[:len(presets.ORDER)] == list(presets.ORDER)
    for p in listed:
        cfg = p.config(seed=5)
        assert cfg.seed == 5
        cfg.map_width, cfg.map_height = 40, 30  # keep the smoke run quick
        cfg.initial_minions = min(cfg.initial_minions, 30)
        sim = Simulation(cfg)
        for _ in range(200):
            sim.step()


def test_preset_values_override_defaults():
    paradise = presets.get("paradies").config()
    assert paradise.initial_predators == 0 and not paradise.predator_immigration
    assert paradise.fruit_energy > SimConfig().fruit_energy
    with pytest.raises(presets.PresetError):
        presets.get("gibt_es_nicht")


def test_user_preset_roundtrip(tmp_path):
    cfg = SimConfig(seed=99, fruit_energy=33.0, initial_predators=7)
    path = presets.save_user_preset("Meine Wüste", cfg, user_dir=tmp_path)
    assert path.name == "meine_wueste.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["werte"] == {"fruit_energy": 33.0, "initial_predators": 7}  # only changes, no seed
    mine = next(p for p in presets.list_presets(tmp_path) if p.name == "meine_wueste")
    assert not mine.builtin and mine.config().fruit_energy == 33.0


def test_broken_or_unknown_user_presets_are_skipped(tmp_path):
    (tmp_path / "kaputt.json").write_text("{nicht json")
    (tmp_path / "fremd.json").write_text(json.dumps({"werte": {"gibt_es_nicht": 1}}))
    names = [p.name for p in presets.list_presets(tmp_path)]
    assert "kaputt" not in names and "fremd" not in names


# ---------------------------------------------------------------- command line


def test_cli_headless_run_exports_and_saves(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    main(["--headless", "--preset", "paradies", "--width", "40", "--height", "30",
          "--minions", "20", "--ticks", "500", "--export", "--save", "stand.lifesim"])  # fmt: skip
    out = capsys.readouterr().out
    assert "Gespeichert" in out and "Exportiert" in out
    assert len(list((tmp_path / "exports").glob("*.csv"))) == 2
    loaded = savefile.load(tmp_path / "stand.lifesim")
    assert loaded.tick > 500 and loaded.config.initial_predators == 0

    main(["--headless", "--load", "stand.lifesim", "--ticks", "100"])
    assert "100 Ticks" in capsys.readouterr().out


def test_cli_reports_bad_input(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit, match="nicht gefunden"):
        main(["--headless", "--preset", "gibt_es_nicht"])
    (tmp_path / "x.lifesim").write_text("kaputt")
    with pytest.raises(SystemExit, match="kein lesbarer Spielstand"):
        main(["--headless", "--load", "x.lifesim"])
