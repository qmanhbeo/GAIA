# main.py
from __future__ import annotations

import argparse
import json

from gaia_config import LEGACY_MODE, SimulationConfig
from simulation import SimulationEngine


def _coerce_config(
    config: SimulationConfig | dict | None = None,
    *,
    days: int = 300,
    seed: int = 42,
    num_households: int = 1,
    members_per_household: int = 20,
    snapshot_frequency: int = 0,
) -> SimulationConfig:
    if isinstance(config, SimulationConfig):
        return config
    if isinstance(config, dict):
        return SimulationConfig.from_dict(config)
    return SimulationConfig(
        days=days,
        seed=seed,
        num_households=num_households,
        members_per_household=members_per_household,
        mode=LEGACY_MODE,
        snapshot_frequency=snapshot_frequency,
    )


def run_simulation(
    config: SimulationConfig | dict | None = None,
    *,
    days: int = 300,
    seed: int = 42,
    num_households: int = 1,
    members_per_household: int = 20,
    snapshot_frequency: int = 0,
):
    resolved_config = _coerce_config(
        config,
        days=days,
        seed=seed,
        num_households=num_households,
        members_per_household=members_per_household,
        snapshot_frequency=snapshot_frequency,
    )
    sim = SimulationEngine(config=resolved_config)
    return sim.run()


def run_simulation_artifact(
    config: SimulationConfig | dict | None = None,
    *,
    days: int = 300,
    seed: int = 42,
    num_households: int = 1,
    members_per_household: int = 20,
    snapshot_frequency: int = 0,
):
    resolved_config = _coerce_config(
        config,
        days=days,
        seed=seed,
        num_households=num_households,
        members_per_household=members_per_household,
        snapshot_frequency=snapshot_frequency,
    )
    sim = SimulationEngine(config=resolved_config)
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
        mode=LEGACY_MODE,
        snapshot_frequency=args.snapshots,
    )
    if args.artifact:
        res = run_simulation_artifact(config=config).to_dict()
    else:
        res = run_simulation(config=config)
    _write_json(args.out, res)
    print(f"Wrote {args.out}")
