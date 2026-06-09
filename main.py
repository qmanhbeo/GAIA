from __future__ import annotations

import argparse
import json
from dataclasses import replace
from typing import Any

from gaia_config import SPATIAL_MODE, SimulationConfig
from spatial_simulation import SpatialPrototypeEngine


def _coerce_config(
    config: SimulationConfig | dict[str, Any] | None = None,
    *,
    days: int = 300,
    seed: int = 42,
    num_households: int = 1,
    members_per_household: int = 20,
    snapshot_frequency: int = 0,
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
            snapshot_frequency=snapshot_frequency,
            grid_width=grid_width,
            grid_height=grid_height,
        )
    if resolved.snapshot_frequency == 0:
        resolved = replace(resolved, snapshot_frequency=1)
    return resolved


def build_engine(config: SimulationConfig | dict[str, Any] | None = None, **overrides: Any) -> SpatialPrototypeEngine:
    return SpatialPrototypeEngine(config=_coerce_config(config, **overrides))


def run_simulation(
    config: SimulationConfig | dict[str, Any] | None = None,
    *,
    days: int = 300,
    seed: int = 42,
    num_households: int = 1,
    members_per_household: int = 20,
    snapshot_frequency: int = 0,
    grid_width: int = 24,
    grid_height: int = 16,
) -> dict[str, list[Any]]:
    engine = build_engine(
        config,
        days=days,
        seed=seed,
        num_households=num_households,
        members_per_household=members_per_household,
        snapshot_frequency=snapshot_frequency,
        grid_width=grid_width,
        grid_height=grid_height,
    )
    return engine.run()


def run_simulation_artifact(
    config: SimulationConfig | dict[str, Any] | None = None,
    *,
    days: int = 300,
    seed: int = 42,
    num_households: int = 1,
    members_per_household: int = 20,
    snapshot_frequency: int = 0,
    grid_width: int = 24,
    grid_height: int = 16,
):
    engine = build_engine(
        config,
        days=days,
        seed=seed,
        num_households=num_households,
        members_per_household=members_per_household,
        snapshot_frequency=snapshot_frequency,
        grid_width=grid_width,
        grid_height=grid_height,
    )
    return engine.run_artifact()


def _write_json(path: str, payload: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the active spatial GAIA world.")
    parser.add_argument("--days", type=int, default=300, help="Maximum ticks to run; one tick is one hour.")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--households", type=int, default=1)
    parser.add_argument("--members", type=int, default=20)
    parser.add_argument("--grid-width", type=int, default=24)
    parser.add_argument("--grid-height", type=int, default=16)
    parser.add_argument("--snapshots", type=int, default=1, help="Snapshot frequency for headless/artifact runs.")
    parser.add_argument("--out", type=str, default=None, help="Optional JSON output path for headless or artifact runs.")
    parser.add_argument(
        "--artifact",
        action="store_true",
        help="Write a structured spatial artifact instead of opening the Pygame view.",
    )
    parser.add_argument(
        "--headless",
        "--no-view",
        dest="headless",
        action="store_true",
        help="Run without opening Pygame. Useful for tests and smoke checks.",
    )
    return parser.parse_args()


def _config_from_args(args: argparse.Namespace) -> SimulationConfig:
    return SimulationConfig(
        days=args.days,
        seed=args.seed,
        num_households=args.households,
        members_per_household=args.members,
        mode=SPATIAL_MODE,
        snapshot_frequency=args.snapshots,
        grid_width=args.grid_width,
        grid_height=args.grid_height,
    )


def main() -> None:
    args = parse_args()
    config = _config_from_args(args)

    if args.artifact:
        payload = run_simulation_artifact(config=config).to_dict()
        out_path = args.out or "out.json"
        _write_json(out_path, payload)
        print(f"Wrote {out_path}")
        return

    if args.headless:
        results = run_simulation(config=config)
        if args.out:
            _write_json(args.out, results)
            print(f"Wrote {args.out}")
        final_population = results["population"][-1] if results["population"] else 0
        final_hunger = results["avg_hunger"][-1] if results["avg_hunger"] else 0.0
        print(
            f"Ran spatial GAIA headless for {args.days} ticks "
            f"(population={final_population}, avg_hunger={final_hunger:.3f})"
        )
        return

    from view.pygame_app import run_pygame_app

    run_pygame_app(engine=SpatialPrototypeEngine(config=config))


if __name__ == "__main__":
    main()
