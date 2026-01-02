# main.py
from simulation import SimulationEngine
import argparse, json, random

def run_simulation(days: int = 300, seed: int = 42,
                   num_households: int = 1, members_per_household: int = 20):
    random.seed(seed)
    sim = SimulationEngine(num_households=num_households,
                           members_per_household=members_per_household,
                           days=days)
    results = sim.run()  # dict-of-lists
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=300)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=str, default="out.json")
    parser.add_argument("--households", type=int, default=1)
    parser.add_argument("--members", type=int, default=20)
    args = parser.parse_args()

    res = run_simulation(days=args.days, seed=args.seed,
                         num_households=args.households,
                         members_per_household=args.members)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(res, f)
    print(f"Wrote {args.out}")
