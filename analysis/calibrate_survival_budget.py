"""Calibration sweep for GAIA physiology parameters.

Runs multiple deterministic configurations across a grid of physiology
parameter combinations to identify viable ranges under the current
world layout.

Does not modify simulation behavior or default config.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from pathlib import Path
from typing import Any

_THIS_DIR = Path(__file__).resolve().parent
_ROOT = _THIS_DIR.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gaia_config import PhysiologyConfig, SimulationConfig  # noqa: E402
from spatial_simulation import SpatialPrototypeEngine  # noqa: E402


SWEEP_GRID = {
    "hunger_increase_per_tick": [0.016, 0.024, 0.032],
    "thirst_increase_per_tick": [0.020, 0.030, 0.041],
    "hunger_damage_rate": [0.008, 0.016],
    "thirst_damage_rate": [0.011, 0.022],
}

FIXED_FIELDS = {
    "hunger_damage_threshold": 0.88,
    "thirst_damage_threshold": 0.91,
    "home_health_regen_per_tick": 0.012,
}


def _events_summary(event_log: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in event_log:
        event = entry["event"]
        counts[event] = counts.get(event, 0) + 1
    return counts


def run_sweep(
    days: int = 100,
    num_households: int = 1,
    members_per_household: int = 20,
    seed: int = 42,
    grid_width: int = 24,
    grid_height: int = 16,
) -> list[dict[str, Any]]:
    keys = list(SWEEP_GRID.keys())
    values = list(SWEEP_GRID.values())
    results: list[dict[str, Any]] = []

    combination_count = len(list(itertools.product(*values)))
    print(f"Running {combination_count} combinations...")
    start = time.time()

    for combo in itertools.product(*values):
        params = dict(zip(keys, combo))
        phys = PhysiologyConfig(**params, **FIXED_FIELDS)

        config = SimulationConfig(
            days=days,
            seed=seed,
            num_households=num_households,
            members_per_household=members_per_household,
            grid_width=grid_width,
            grid_height=grid_height,
            physiology=phys,
        )

        engine = SpatialPrototypeEngine(config=config)
        initial_pop = len([a for a in engine.agents if a.is_alive()])

        engine.run()

        event_counts = _events_summary(engine.event_log)

        time_series = engine.time_series
        final_pop = time_series["population"][-1] if time_series["population"] else 0
        min_water = min(time_series["water_stock"]) if time_series["water_stock"] else 0.0
        min_food = min(time_series["food_stock"]) if time_series["food_stock"] else 0.0
        min_home_food = min(time_series["total_home_food"]) if time_series["total_home_food"] else 0.0
        deaths = event_counts.get("agent_died", 0)

        drink = event_counts.get("drink", 0)
        gather = event_counts.get("gather_food", 0)
        deposit = event_counts.get("deposit_food", 0)
        eat_home = event_counts.get("eat_at_home", 0)
        loop_completed = gather > 0 and deposit > 0 and eat_home > 0

        score = 0
        score += 1 if drink > 0 else 0
        score += 1 if gather > 0 else 0
        score += 1 if deposit > 0 else 0
        score += 1 if eat_home > 0 else 0
        score += 1 if loop_completed else 0

        # Penalty for all dying very early (before tick 20)
        early_exit = False
        if len(time_series["population"]) >= 20:
            early_exit = all(p == 0 for p in time_series["population"][:20])
        else:
            early_exit = final_pop == 0
        if early_exit:
            score -= 1

        results.append({
            "params": params,
            "score": score,
            "final_population": f"{final_pop} / {initial_pop}",
            "deaths": deaths,
            "drink_events": drink,
            "gather_food_events": gather,
            "deposit_food_events": deposit,
            "eat_at_home_events": eat_home,
            "loop_completed": loop_completed,
            "min_water_stock": round(min_water, 3),
            "min_food_stock": round(min_food, 3),
            "min_home_food": round(min_home_food, 3),
        })

    elapsed = time.time() - start
    print(f"Completed {combination_count} runs in {elapsed:.1f}s\n")

    results.sort(key=lambda r: (-r["score"], -r["deaths"]))
    return results


def print_ranked(results: list[dict[str, Any]], top_n: int = 10) -> None:
    header = f"{'#':>3} {'score':>5} {'hunger_inc':>10} {'thirst_inc':>10} {'hunger_dmg':>9} {'thirst_dmg':>10} {'pop':>8} {'drink':>5} {'gath':>4} {'dep':>4} {'eat':>4} {'loop':>4} {'water_min':>8}"
    print("=" * len(header))
    print("Calibration Sweep — Ranked Results")
    print("=" * len(header))
    print(header)
    print("-" * len(header))

    for i, r in enumerate(results[:top_n]):
        p = r["params"]
        print(
            f"{i + 1:>3} {r['score']:>5} "
            f"{p['hunger_increase_per_tick']:>10.3f} "
            f"{p['thirst_increase_per_tick']:>10.3f} "
            f"{p['hunger_damage_rate']:>9.3f} "
            f"{p['thirst_damage_rate']:>10.3f} "
            f"{r['final_population']:>8} "
            f"{r['drink_events']:>5} "
            f"{r['gather_food_events']:>4} "
            f"{r['deposit_food_events']:>4} "
            f"{r['eat_at_home_events']:>4} "
            f"{'yes' if r['loop_completed'] else ' no':>4} "
            f"{r['min_water_stock']:>8.3f}"
        )

    print("-" * len(header))
    bottom = min(3, len([r for r in results if r["score"] <= 0]))
    if bottom:
        print(f"\nBottom {bottom} (non-viable):")
        for r in results[-bottom:]:
            p = r["params"]
            print(
                f"  score={r['score']} "
                f"hunger_inc={p['hunger_increase_per_tick']:.3f} "
                f"thirst_inc={p['thirst_increase_per_tick']:.3f} "
                f"hunger_dmg={p['hunger_damage_rate']:.3f} "
                f"thirst_dmg={p['thirst_damage_rate']:.3f} "
                f"pop={r['final_population']} "
                f"drink={r['drink_events']} "
                f"loop={r['loop_completed']}"
            )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GAIA physiology calibration sweep")
    parser.add_argument("--days", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--households", type=int, default=1)
    parser.add_argument("--members", type=int, default=20)
    parser.add_argument("--grid-width", type=int, default=24)
    parser.add_argument("--grid-height", type=int, default=16)
    parser.add_argument("--out", type=str, default=None, help="JSON output path")
    parser.add_argument("--top", type=int, default=10, help="Number of top results to show")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    results = run_sweep(
        days=args.days,
        num_households=args.households,
        members_per_household=args.members,
        seed=args.seed,
        grid_width=args.grid_width,
        grid_height=args.grid_height,
    )
    print_ranked(results, top_n=args.top)

    if args.out:
        with open(args.out, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
