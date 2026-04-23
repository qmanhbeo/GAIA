from __future__ import annotations

import unittest

from assumptions import LegacyAssumptions
from gaia_config import LEGACY_MODE, SPATIAL_MODE, SimulationConfig
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

    def test_spatial_artifact_contains_replay_snapshots(self):
        config = SimulationConfig(
            days=6,
            seed=17,
            num_households=1,
            members_per_household=3,
            mode=SPATIAL_MODE,
            grid_width=12,
            grid_height=8,
        )
        artifact = run_simulation_artifact(config=config).to_dict()

        self.assertEqual(artifact["metadata"]["mode"], SPATIAL_MODE)
        self.assertEqual(artifact["metadata"]["viewer_kind"], "pixi_spatial_replay_v1")
        self.assertEqual(artifact["snapshots"][0]["tick"], 0)
        self.assertEqual(artifact["snapshots"][-1]["tick"], 6)
        self.assertIn("agents", artifact["snapshots"][-1])
        self.assertIn("nodes", artifact["snapshots"][-1])
        self.assertEqual(artifact["final_state"]["grid"]["width"], 12)

    def test_spatial_mode_is_deterministic(self):
        config = SimulationConfig(
            days=10,
            seed=21,
            num_households=2,
            members_per_household=2,
            mode=SPATIAL_MODE,
            grid_width=14,
            grid_height=10,
        )
        first = run_simulation_artifact(config=config).to_dict()
        second = run_simulation_artifact(config=config).to_dict()
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
