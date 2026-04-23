# main.py
from __future__ import annotations

import argparse
import json
from dataclasses import replace

from gaia_config import LEGACY_MODE, SPATIAL_MODE, SimulationConfig
from simulation import SimulationEngine
from spatial_simulation import SpatialPrototypeEngine


def _coerce_config(
    config: SimulationConfig | dict | None = None,
    *,
    days: int = 300,
    seed: int = 42,
    num_households: int = 1,
    members_per_household: int = 20,
    snapshot_frequency: int = 0,
    mode: str = LEGACY_MODE,
    grid_width: int = 24,
    grid_height: int = 16,
) -> SimulationConfig:
    if isinstance(config, SimulationConfig):
        resolved = config
    elif isinstance(config, dict):
        resolved = SimulationConfig.from_dict(config)
    else:
        resolved = SimulationConfig(
            days=days,
            seed=seed,
            num_households=num_households,
            members_per_household=members_per_household,
            mode=mode,
            snapshot_frequency=snapshot_frequency,
            grid_width=grid_width,
            grid_height=grid_height,
        )
    if resolved.mode == SPATIAL_MODE and resolved.snapshot_frequency == 0:
        resolved = replace(resolved, snapshot_frequency=1)
    return resolved


def _build_engine(config: SimulationConfig):
    if config.mode == SPATIAL_MODE:
        return SpatialPrototypeEngine(config=config)
    return SimulationEngine(config=config)


def run_simulation(
    config: SimulationConfig | dict | None = None,
    *,
    days: int = 300,
    seed: int = 42,
    num_households: int = 1,
    members_per_household: int = 20,
    snapshot_frequency: int = 0,
    mode: str = LEGACY_MODE,
    grid_width: int = 24,
    grid_height: int = 16,
):
    resolved_config = _coerce_config(
        config,
        days=days,
        seed=seed,
        num_households=num_households,
        members_per_household=members_per_household,
        snapshot_frequency=snapshot_frequency,
        mode=mode,
        grid_width=grid_width,
        grid_height=grid_height,
    )
    sim = _build_engine(resolved_config)
    return sim.run()


def run_simulation_artifact(
    config: SimulationConfig | dict | None = None,
    *,
    days: int = 300,
    seed: int = 42,
    num_households: int = 1,
    members_per_household: int = 20,
    snapshot_frequency: int = 0,
    mode: str = LEGACY_MODE,
    grid_width: int = 24,
    grid_height: int = 16,
):
    resolved_config = _coerce_config(
        config,
        days=days,
        seed=seed,
        num_households=num_households,
        members_per_household=members_per_household,
        snapshot_frequency=snapshot_frequency,
        mode=mode,
        grid_width=grid_width,
        grid_height=grid_height,
    )
    sim = _build_engine(resolved_config)
    return sim.run_artifact()


def _write_json(path: str, payload):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=300)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=str, default="out.json")
    parser.add_argument("--households", type=int, default=1)
    parser.add_argument("--members", type=int, default=20)
    parser.add_argument("--snapshots", type=int, default=0)
    parser.add_argument("--mode", type=str, default=LEGACY_MODE, choices=[LEGACY_MODE, SPATIAL_MODE])
    parser.add_argument("--grid-width", type=int, default=24)
    parser.add_argument("--grid-height", type=int, default=16)
    parser.add_argument(
        "--artifact",
        action="store_true",
        help="Write a structured run artifact with metadata, time series, and snapshots.",
    )
    args = parser.parse_args()

    config = SimulationConfig(
        days=args.days,
        seed=args.seed,
        num_households=args.households,
        members_per_household=args.members,
        mode=args.mode,
        snapshot_frequency=args.snapshots,
        grid_width=args.grid_width,
        grid_height=args.grid_height,
    )
    if args.artifact:
        res = run_simulation_artifact(config=config).to_dict()
    else:
        res = run_simulation(config=config)
    _write_json(args.out, res)
    print(f"Wrote {args.out}")
