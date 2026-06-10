"""Survival-budget audit for GAIA.

Computes per-agent physiological time budgets and travel estimates
to diagnose why agents fail or survive under current engine parameters.
Does not modify simulation behavior.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import median
from typing import Any

# Ensure workspace root is importable (handles both `python analysis/...py` and `python -m analysis.audit...`)
_THIS_DIR = Path(__file__).resolve().parent
_ROOT = _THIS_DIR.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gaia_config import SimulationConfig  # noqa: E402
from spatial_simulation import SpatialPrototypeEngine  # noqa: E402


# ---------------------------------------------------------------------------
# Physiological constants (mirrored from spatial_simulation._update_agent)
#   hunger_per_tick         = 0.032   (line 650)
#   thirst_per_tick         = 0.041   (line 651)
#   hunger_critical         = 0.88    (line 652)
#   thirst_critical         = 0.91    (line 654)
#   hunger_damage_per_tick  = 0.016   (line 653)
#   thirst_damage_per_tick  = 0.022   (line 655)
#   home_health_regen       = 0.012   (line 633)
# ---------------------------------------------------------------------------


def _ticks_until_critical(current: float, rate: float, threshold: float) -> int:
    if current >= threshold:
        return 0
    return int((threshold - current) / rate) + 1


def project_death_tick(hunger: float, thirst: float, health: float) -> int:
    ticks = 0
    h, t, hp = hunger, thirst, health
    while hp > 0 and ticks < 100_000:
        h = min(1.0, h + 0.032)
        t = min(1.0, t + 0.041)
        if h > 0.88:
            hp = max(0.0, hp - 0.016)
        if t > 0.91:
            hp = max(0.0, hp - 0.022)
        if hp <= 0:
            break
        ticks += 1
    return ticks


def _path_ticks(engine: SpatialPrototypeEngine, start: tuple[int, int], goal_node: Any) -> int | None:
    if start == (goal_node.x, goal_node.y):
        return 0
    path = engine._find_path(start, (goal_node.x, goal_node.y), {})
    if path is None:
        return None
    return len(path) - 1


def _survivable(dist: int | None, budget: int | None) -> bool:
    return dist is not None and budget is not None and dist <= budget


# ---------------------------------------------------------------------------
# Per-agent budget computation
# ---------------------------------------------------------------------------

def compute_agent_budget(engine: SpatialPrototypeEngine, agent: Any) -> dict[str, Any]:
    pos = (agent.x, agent.y)
    home = engine._home_for_agent(agent)
    food = engine._node_by_kind("food")
    water = engine._node_by_kind("water")

    task_target = None
    if agent.current_task is not None and agent.task_target_id is not None:
        task_target = next(
            (n for n in engine.nodes if n.id == agent.task_target_id), None
        )

    d_home = _path_ticks(engine, pos, home)
    d_food = _path_ticks(engine, pos, food)
    d_water = _path_ticks(engine, pos, water)
    d_target = _path_ticks(engine, pos, task_target) if task_target else None

    h_crit = _ticks_until_critical(agent.hunger, 0.032, 0.88)
    t_crit = _ticks_until_critical(agent.thirst, 0.041, 0.91)
    death_t = project_death_tick(agent.hunger, agent.thirst, agent.health)

    can_hunger = _survivable(d_target, h_crit) if d_target is not None else None
    can_thirst = _survivable(d_target, t_crit) if d_target is not None else None
    can_death = _survivable(d_target, death_t) if d_target is not None else None

    distances = {"home": d_home, "food": d_food, "water": d_water}
    viable = {k: v for k, v in distances.items() if v is not None}
    nearest = min(viable, key=viable.get) if viable else None

    is_current_survivable = can_death is True
    should_reconsider = agent.current_task is not None and not is_current_survivable

    reason = ""
    if should_reconsider:
        if d_target is not None and t_crit is not None and d_target > t_crit:
            reason = "current target too far before thirst critical"
        elif d_target is not None and h_crit is not None and d_target > h_crit:
            reason = "current target too far before hunger critical"
        else:
            reason = "current target not survivable"
        if nearest and _survivable(distances[nearest], death_t):
            reason += f", {nearest} reachable before death"
        else:
            reason += ", no resource reachable before death"

    return {
        "agent_id": agent.id,
        "agent_label": agent.label,
        "tick": engine.tick,
        "position": (agent.x, agent.y),
        "current_task": agent.current_task,
        "task_target_id": agent.task_target_id,
        "hunger": round(agent.hunger, 4),
        "thirst": round(agent.thirst, 4),
        "health": round(agent.health, 4),
        "carried_food": round(agent.carried_food, 4),
        "distance_to_home": d_home,
        "distance_to_food": d_food,
        "distance_to_water": d_water,
        "distance_to_current_target": d_target,
        "estimated_ticks_to_home": d_home,
        "estimated_ticks_to_food": d_food,
        "estimated_ticks_to_water": d_water,
        "estimated_ticks_to_current_target": d_target,
        "ticks_until_hunger_critical": h_crit,
        "ticks_until_thirst_critical": t_crit,
        "ticks_until_hunger_damage": h_crit,
        "ticks_until_thirst_damage": t_crit,
        "estimated_ticks_until_death_if_no_consumption": death_t,
        "can_reach_current_target_before_hunger_critical": can_hunger,
        "can_reach_current_target_before_thirst_critical": can_thirst,
        "can_reach_current_target_before_death": can_death,
        "current_task_survivable": is_current_survivable,
        "nearest_viable_resource": nearest,
        "should_reconsider_by_survival_budget": should_reconsider,
        "reason": reason,
    }


# ---------------------------------------------------------------------------
# Full config audit
# ---------------------------------------------------------------------------

def audit_config(config: SimulationConfig) -> dict[str, Any]:
    engine = SpatialPrototypeEngine(config=config)
    initial_budgets = [
        compute_agent_budget(engine, agent)
        for agent in engine.agents
        if agent.is_alive()
    ]

    engine.run()

    final_budgets = [
        compute_agent_budget(engine, agent)
        for agent in engine.agents
        if agent.is_alive()
    ]

    events = engine.event_log
    drink_events = sum(1 for e in events if e["event"] == "drink")
    gather_events = sum(1 for e in events if e["event"] == "gather_food")
    deaths = sum(1 for e in events if e["event"] == "agent_died")
    total_pop = len(engine.agents)
    final_pop = sum(1 for a in engine.agents if a.is_alive())

    total = len(initial_budgets) or 1
    water_ok = sum(
        1 for b in initial_budgets
        if b["distance_to_water"] is not None
        and b["distance_to_water"] <= b["ticks_until_thirst_critical"]
    )
    food_ok = sum(
        1 for b in initial_budgets
        if b["distance_to_food"] is not None
        and b["distance_to_food"] <= b["ticks_until_hunger_critical"]
    )

    food_home_ticks = None
    if initial_budgets:
        food_node = engine._node_by_kind("food")
        home_node = engine._home_for_agent(engine.agents[0])
        food_home_ticks = _path_ticks(engine, (food_node.x, food_node.y), home_node)

    loop_ok = False
    if food_home_ticks is not None and initial_budgets:
        d_food_vals = [b["distance_to_food"] for b in initial_budgets if b["distance_to_food"] is not None]
        death_vals = [b["estimated_ticks_until_death_if_no_consumption"] for b in initial_budgets]
        if d_food_vals and death_vals:
            d_food_med = median(d_food_vals)
            death_med = median(death_vals)
            loop_ok = (d_food_med + food_home_ticks) <= death_med

    bottleneck = "unknown"
    if water_ok < total:
        bottleneck = "thirst decay / distance to water"
    elif food_ok < total:
        bottleneck = "hunger decay / distance to food"
    elif not loop_ok:
        bottleneck = "travel distance / combined loop time exceeds death budget"
    elif final_pop == 0:
        bottleneck = "health damage accumulation / resource depletion"

    return {
        "config": {
            "num_households": config.num_households,
            "members_per_household": config.members_per_household,
            "grid_width": config.grid_width,
            "grid_height": config.grid_height,
            "days": config.days,
            "seed": config.seed,
        },
        "final_population": f"{final_pop} / {total_pop}",
        "drink_events": drink_events,
        "gather_events": gather_events,
        "deaths": deaths,
        "initial_budgets": initial_budgets,
        "final_budgets": final_budgets,
        "bottleneck": bottleneck,
        "food_home_ticks": food_home_ticks,
        "water_reachable_at_spawn": f"{water_ok}/{total}",
        "food_reachable_at_spawn": f"{food_ok}/{total}",
        "loop_survivable": loop_ok,
    }


def _median_or_na(values: list[int | None]) -> float | str:
    vals = [v for v in values if v is not None]
    if not vals:
        return "N/A"
    return round(median(vals), 1)


def print_report(results: dict[str, Any]) -> None:
    cfg = results["config"]
    print("=" * 52)
    print("Survival Budget Audit")
    print("=" * 52)
    print(f"Config: {cfg['num_households']} households x {cfg['members_per_household']} members")
    print(f"  grid {cfg['grid_width']}x{cfg['grid_height']}, {cfg['days']} days, seed={cfg['seed']}")
    print(f"Final population: {results['final_population']}")
    print(f"Drink events: {results['drink_events']}")
    print(f"Gather events: {results['gather_events']}")
    print(f"Deaths: {results['deaths']}")
    print()

    budgets = results["initial_budgets"]
    if not budgets:
        print("No agents to audit.")
        return

    d_home_vals = [b["distance_to_home"] for b in budgets]
    d_food_vals = [b["distance_to_food"] for b in budgets]
    d_water_vals = [b["distance_to_water"] for b in budgets]

    print("Travel estimates (median at spawn):")
    print(f"  estimated_ticks_to_home:  {_median_or_na(d_home_vals)}")
    print(f"  estimated_ticks_to_food:  {_median_or_na(d_food_vals)}")
    print(f"  estimated_ticks_to_water: {_median_or_na(d_water_vals)}")
    if results["food_home_ticks"] is not None:
        print(f"  food_to_home_ticks:       {results['food_home_ticks']}")
    print()

    h_crit_vals = [b["ticks_until_hunger_critical"] for b in budgets]
    t_crit_vals = [b["ticks_until_thirst_critical"] for b in budgets]
    death_vals = [b["estimated_ticks_until_death_if_no_consumption"] for b in budgets]

    print("Physiological budgets (median at spawn):")
    print(f"  ticks_until_thirst_critical: {_median_or_na(t_crit_vals)}")
    print(f"  ticks_until_hunger_critical: {_median_or_na(h_crit_vals)}")
    print(f"  estimated_ticks_until_death: {_median_or_na(death_vals)}")
    print()

    print("Failure diagnosis:")
    print(f"  agents can reach water before thirst critical?  {results['water_reachable_at_spawn']}")
    print(f"  agents can reach food before hunger critical?   {results['food_reachable_at_spawn']}")
    print(f"  agents can complete food->home loop?            {'yes' if results['loop_survivable'] else 'no'}")
    print(f"  likely bottleneck: {results['bottleneck']}")

    print()
    reconsider = [b for b in budgets if b["should_reconsider_by_survival_budget"]]
    if reconsider:
        print(f"  agents that should reconsider: {len(reconsider)}/{len(budgets)}")
        for b in reconsider[:5]:
            print(f"    {b['agent_label']}: {b['reason']}")
        if len(reconsider) > 5:
            print(f"    ... and {len(reconsider) - 5} more")
    print("=" * 52)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GAIA survival-budget audit")
    parser.add_argument("--days", type=int, default=300)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--households", type=int, default=1)
    parser.add_argument("--members", type=int, default=20)
    parser.add_argument("--grid-width", type=int, default=24)
    parser.add_argument("--grid-height", type=int, default=16)
    parser.add_argument("--out", type=str, default=None, help="JSON output path")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    config = SimulationConfig(
        days=args.days,
        seed=args.seed,
        num_households=args.households,
        members_per_household=args.members,
        grid_width=args.grid_width,
        grid_height=args.grid_height,
    )
    results = audit_config(config)
    print_report(results)

    if args.out:
        with open(args.out, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
