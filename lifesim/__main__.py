"""Entry point: python -m lifesim [--headless --ticks N]"""

from __future__ import annotations

import argparse
import time

from lifesim.config import SimConfig


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="lifesim", description="Simulator für Leben und Evolution")
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--minions", type=int, default=None, help="Startanzahl Minions")
    p.add_argument("--width", type=int, default=None, help="Kartenbreite in Kacheln")
    p.add_argument("--height", type=int, default=None, help="Kartenhöhe in Kacheln")
    p.add_argument("--headless", action="store_true", help="Ohne Grafik laufen lassen")
    p.add_argument("--ticks", type=int, default=100000, help="Anzahl Ticks im Headless-Modus")
    return p.parse_args()


def build_config(args: argparse.Namespace) -> SimConfig:
    cfg = SimConfig()
    if args.seed is not None:
        cfg.seed = args.seed
    if args.minions is not None:
        cfg.initial_minions = args.minions
    if args.width is not None:
        cfg.map_width = args.width
    if args.height is not None:
        cfg.map_height = args.height
    return cfg


def run_headless(cfg: SimConfig, ticks: int) -> None:
    from lifesim.agents.minion import DeathCause
    from lifesim.core.simulation import Simulation

    sim = Simulation(cfg)
    start = time.perf_counter()
    report_every = max(1, ticks // 20)
    for _ in range(ticks):
        sim.step()
        if sim.tick % report_every == 0:
            row = sim.history[-1]
            print(
                f"Tag {sim.clock.day:>4} {sim.clock.season_name:<8} pop {len(sim.minions):>4}  "
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
        f"Altersschwäche {sim.deaths[DeathCause.OLD_AGE]}"
    )
    print(f"{sim.tick} Ticks in {elapsed:.1f}s ({sim.tick / max(elapsed, 1e-9):.0f} Ticks/s)")


def main() -> None:
    args = parse_args()
    cfg = build_config(args)
    if args.headless:
        run_headless(cfg, args.ticks)
    else:
        from lifesim.ui.app import App

        App(cfg).run()


if __name__ == "__main__":
    main()
