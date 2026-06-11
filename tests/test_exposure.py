from __future__ import annotations

import unittest

from gaia_config import PhysiologyConfig, SimulationConfig
from spatial_simulation import SpatialPrototypeEngine, SpatialTile


class ExposureScaffoldTests(unittest.TestCase):
    def setUp(self):
        self.config = SimulationConfig(
            days=5, seed=10, num_households=1, members_per_household=2,
            grid_width=12, grid_height=10,
            physiology=PhysiologyConfig(
                exposure_increase_per_tick_away_from_home=0.05,
                exposure_recovery_per_tick_at_home=0.10,
            ),
        )
        self.engine = SpatialPrototypeEngine(config=self.config)
        self.agent = self.engine.agents[0]
        self.home = self.engine._home_for_agent(self.agent)

    def test_agent_starts_with_zero_exposure(self):
        self.assertEqual(self.agent.exposure, 0.0)

    def test_exposure_increases_away_from_home(self):
        self.agent.x = self.home.x + 5
        self.agent.y = self.home.y
        self.engine.step()
        self.assertGreater(self.agent.exposure, 0.0)

    def test_exposure_recovers_at_home(self):
        self.agent.exposure = 0.5
        self.agent.x = self.home.x
        self.agent.y = self.home.y
        self.engine.step()
        self.assertLess(self.agent.exposure, 0.5)

    def test_exposure_clamped_above(self):
        self.agent.x = self.home.x + 5
        self.agent.y = self.home.y
        self.agent.exposure = 0.99
        for _ in range(5):
            self.engine.step()
        self.assertLessEqual(self.agent.exposure, 1.0)

    def test_exposure_clamped_below(self):
        self.agent.x = self.home.x
        self.agent.y = self.home.y
        self.agent.exposure = 0.1
        for _ in range(5):
            self.engine.step()
        self.assertGreaterEqual(self.agent.exposure, 0.0)

    def test_time_series_has_exposure_metrics_after_step(self):
        self.engine.step()
        self.assertIn("avg_exposure", self.engine.time_series)
        self.assertIn("max_exposure", self.engine.time_series)
        self.assertEqual(len(self.engine.time_series["avg_exposure"]), 1)

    def test_avg_exposure_is_within_bounds(self):
        for _ in range(5):
            self.engine.step()
        for v in self.engine.time_series["avg_exposure"]:
            self.assertIsInstance(v, float)
            self.assertGreaterEqual(v, 0.0)
            self.assertLessEqual(v, 1.0)

    def test_max_exposure_is_within_bounds(self):
        for _ in range(5):
            self.engine.step()
        for v in self.engine.time_series["max_exposure"]:
            self.assertIsInstance(v, float)
            self.assertGreaterEqual(v, 0.0)
            self.assertLessEqual(v, 1.0)

    def test_snapshot_metrics_include_exposure_fields(self):
        snapshot = self.engine.snapshot()
        m = snapshot["metrics"]
        self.assertIn("avg_exposure", m)
        self.assertIn("max_exposure", m)
        self.assertIn("avg_exposure", snapshot)
        self.assertIn("max_exposure", snapshot)

    def test_exposure_serialized_in_agent_dict(self):
        d = self.agent.as_dict()
        self.assertIn("exposure", d)
        self.assertIsInstance(d["exposure"], float)


class TileExposurePressureTests(unittest.TestCase):
    def setUp(self):
        self.config = SimulationConfig(
            days=5, seed=10, num_households=1, members_per_household=2,
            grid_width=12, grid_height=10,
        )
        self.engine = SpatialPrototypeEngine(config=self.config)
        self.agent = self.engine.agents[0]
        self.home = self.engine._home_for_agent(self.agent)

    def test_tile_snapshot_includes_exposure_pressure(self):
        tile = next(iter(self.engine.tiles.values()))
        d = tile.as_dict()
        self.assertIn("exposure_pressure", d)

    def test_home_tile_pressure_zero(self):
        tile = self.engine.tiles[(self.home.x, self.home.y)]
        self.assertEqual(tile.exposure_pressure, 0.0)

    def test_marsh_pressure_higher_than_plain(self):
        marsh = self._tile_by_kind("marsh")
        plain = self._tile_by_kind("plain")
        self.assertGreater(marsh.exposure_pressure, plain.exposure_pressure)

    def test_road_pressure_lower_than_plain(self):
        road = self._tile_by_kind("road")
        plain = self._tile_by_kind("plain")
        self.assertLess(road.exposure_pressure, plain.exposure_pressure)

    def test_marsh_accumulates_faster_than_plain(self):
        marsh_tile = self._tile_by_kind("marsh")
        plain_tile = self._tile_by_kind("plain")

        self.agent.x, self.agent.y = plain_tile.x, plain_tile.y
        self.agent.exposure = 0.0
        self.engine.step()
        plain_gain = self.agent.exposure

        self.agent.x, self.agent.y = marsh_tile.x, marsh_tile.y
        self.agent.exposure = 0.0
        self.engine.step()
        marsh_gain = self.agent.exposure

        self.assertGreater(marsh_gain, plain_gain)

    def test_exposure_clamped_above_with_tile_pressure(self):
        away = self._tile_by_kind("plain")
        self.agent.x, self.agent.y = away.x, away.y
        self.agent.exposure = 0.99
        for _ in range(5):
            self.engine.step()
        self.assertLessEqual(self.agent.exposure, 1.0)

    def test_exposure_recovers_at_home_with_tile_pressure(self):
        self.agent.exposure = 0.5
        self.agent.x, self.agent.y = self.home.x, self.home.y
        self.engine.step()
        self.assertLess(self.agent.exposure, 0.5)

    def _tile_by_kind(self, kind: str) -> SpatialTile:
        for tile in self.engine.tiles.values():
            if tile.kind == kind:
                return tile
        raise ValueError(f"No tile of kind {kind}")


if __name__ == "__main__":
    unittest.main()
