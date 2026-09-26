"""Entry point: python -m lifesim [options]. See --help."""

from __future__ import annotations

import argparse
import sys
import time

from lifesim import presets
from lifesim.config import SimConfig


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="lifesim", description="Simulator für Leben und Evolution")
    p.add_argument("--preset", help="Voreinstellung als Grundlage (siehe --list-presets)")
    p.add_argument("--list-presets", action="store_true", help="Voreinstellungen auflisten und beenden")
    p.add_argument("--load", metavar="DATEI", help="Spielstand laden")
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--minions", type=int, default=None, help="Startanzahl Minions")
    p.add_argument("--predators", type=int, default=None, help="Startanzahl Raubtiere")
    p.add_argument("--width", type=int, default=None, help="Kartenbreite in Kacheln")
    p.add_argument("--height", type=int, default=None, help="Kartenhöhe in Kacheln")
    headless = p.add_argument_group("ohne Grafik")
    headless.add_argument("--headless", action="store_true", help="Ohne Grafik laufen lassen")
    headless.add_argument("--ticks", type=int, default=None, help="Anzahl Ticks (Standard: 100000)")
    headless.add_argument("--days", type=float, default=None, help="Anzahl Tage statt Ticks")
    headless.add_argument("--export", action="store_true", help="Am Ende CSV-Dateien nach exports/ schreiben")
    headless.add_argument("--save", metavar="DATEI", help="Am Ende den Spielstand speichern")
    return p.parse_args(argv)


def build_config(args: argparse.Namespace) -> SimConfig:
    cfg = presets.get(args.preset).config() if args.preset else SimConfig()
    overrides = {
        "seed": args.seed,
        "initial_minions": args.minions,
        "initial_predators": args.predators,
        "map_width": args.width,
        "map_height": args.height,
    }
    for key, value in overrides.items():
        if value is not None:
            setattr(cfg, key, value)
    return cfg


def print_presets() -> None:
    for p in presets.list_presets():
        mark = "" if p.builtin else " (eigene)"
        print(f"{p.name:<20} {p.title}{mark}\n{'':<20} {p.description}")


def run_headless(sim, ticks: int, export: bool, save_to: str | None) -> None:
    from lifesim.agents.minion import DeathCause
    from lifesim.persistence import export as csv_export
    from lifesim.persistence import save as savefile

    start = time.perf_counter()
    first = sim.tick
    report_every = max(1, ticks // 20)
    for _ in range(ticks):
        sim.step()
        if (sim.tick - first) % report_every == 0:
            row = sim.history[-1]
            print(
                f"Tag {sim.clock.day:>4} {sim.clock.season_name:<8} pop {len(sim.minions):>4}  "
                f"Raubtiere {len(sim.predators):>2}  Gruppen {row['groups']:>3}  "
                f"gen {row['mean_generation']:5.1f}  Bäume {row['trees']:>4}  "
                f"Früchte {row['fruits']:>4}  speed {row['gene_speed']:.2f}  "
                f"vision {row['gene_vision']:.2f}  energy {row['gene_max_energy']:.2f}  "
                f"lifespan {row['gene_lifespan']:.2f}  fert {row['gene_fertility']:.2f}"
            )
        if not sim.minions:
            print(f"Population ausgestorben bei Tick {sim.tick}.")
            break
    elapsed = time.perf_counter() - start
    print(
        f"Geburten {sim.births}, verhungert {sim.deaths[DeathCause.STARVATION]}, "
        f"Altersschwäche {sim.deaths[DeathCause.OLD_AGE]}, Kampf {sim.deaths[DeathCause.FIGHT]}, "
        f"gefressen {sim.deaths[DeathCause.PREDATOR]}, Raubtiere vertrieben {sim.repelled}"
    )
    done = sim.tick - first
    print(f"{done} Ticks in {elapsed:.1f}s ({done / max(elapsed, 1e-9):.0f} Ticks/s)")
    if export:
        for path in csv_export.export_all(sim):
            print(f"Exportiert: {path}")
    if save_to:
        print(f"Gespeichert: {savefile.save(sim, save_to)}")


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.list_presets:
        print_presets()
        return
    try:
        cfg = build_config(args)
    except presets.PresetError as e:
        sys.exit(f"Fehler: {e}")

    if args.headless:
        from lifesim.core.simulation import Simulation
        from lifesim.persistence import save as savefile

        try:
            sim = savefile.load(args.load) if args.load else Simulation(cfg)
        except savefile.SaveError as e:
            sys.exit(f"Fehler: {e}")
        ticks = args.ticks
        if args.days is not None:
            ticks = int(args.days * sim.config.ticks_per_day)
        run_headless(sim, ticks if ticks is not None else 100_000, args.export, args.save)
    else:
        from lifesim.ui.app import App

        app = App(cfg)
        if args.load:
            app.load_game(args.load)
        app.run()


if __name__ == "__main__":
    main()
