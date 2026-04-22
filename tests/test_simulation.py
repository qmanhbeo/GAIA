from __future__ import annotations

import unittest

from assumptions import LegacyAssumptions
from gaia_config import LEGACY_MODE, SimulationConfig
from main import run_simulation, run_simulation_artifact
from simulation import SimulationEngine


class SimulationConfigTests(unittest.TestCase):
    def test_round_trip_config(self):
        config = SimulationConfig(
            days=12,
            seed=99,
            num_households=3,
            members_per_household=4,
            mode=LEGACY_MODE,
            snapshot_frequency=6,
        )
        rebuilt = SimulationConfig.from_dict(config.to_dict())
        self.assertEqual(config, rebuilt)


class SimulationDeterminismTests(unittest.TestCase):
    def test_same_seed_produces_same_time_series(self):
        config = SimulationConfig(
            days=20,
            seed=123,
            num_households=2,
            members_per_household=5,
        )
        first = run_simulation(config=config)
        second = run_simulation(config=config)
        self.assertEqual(first, second)

    def test_run_artifact_contains_metadata_and_snapshots(self):
        config = SimulationConfig(
            days=10,
            seed=7,
            num_households=1,
            members_per_household=4,
            snapshot_frequency=5,
        )
        artifact = run_simulation_artifact(config=config)
        payload = artifact.to_dict()

        self.assertEqual(payload["metadata"]["mode"], LEGACY_MODE)
        self.assertEqual(payload["metadata"]["config"]["seed"], 7)
        self.assertIn("metric_schema", payload["metadata"])
        self.assertEqual(len(payload["snapshots"]), 2)
        self.assertEqual(payload["final_state"]["day"], 10)

    def test_custom_assumptions_flow_through_config(self):
        config = SimulationConfig(
            days=8,
            seed=3,
            num_households=1,
            members_per_household=3,
            assumptions=LegacyAssumptions(REPRODUCTION_CHANCE=0.0),
        )
        results = run_simulation(config=config)
        self.assertEqual(results["population"][0], results["population"][-1])

    def test_engine_step_returns_structured_snapshot(self):
        engine = SimulationEngine(
            config=SimulationConfig(
                days=5,
                seed=11,
                num_households=1,
                members_per_household=3,
            )
        )
        snapshot = engine.step()
        self.assertEqual(snapshot["day"], 1)
        self.assertIn("population", snapshot)
        self.assertIn("food", snapshot)


if __name__ == "__main__":
    unittest.main()
