from __future__ import annotations

import unittest

from gaia_config import SimulationConfig
from spatial_simulation import (
    CAMP_CAPACITY,
    CAMP_COLOR,
    CAMP_SHELTER_QUALITY_DEFAULT,
    SpatialPrototypeEngine,
    make_camp_node,
)


class CampNodeTests(unittest.TestCase):
    def test_camp_node_can_be_added_to_engine(self):
        config = SimulationConfig(
            days=5, seed=10, num_households=1, members_per_household=1,
            grid_width=12, grid_height=10,
        )
        engine = SpatialPrototypeEngine(config=config)
        camp = make_camp_node("camp-1", x=5, y=5, label="Test Camp")
        engine.nodes.append(camp)
        snapshot = engine.snapshot()
        camp_nodes = [n for n in snapshot["nodes"] if n["kind"] == "camp"]
        self.assertEqual(len(camp_nodes), 1)
        found = camp_nodes[0]
        self.assertEqual(found["id"], "camp-1")
        self.assertEqual(found["label"], "Test Camp")
        self.assertEqual(found["x"], 5)
        self.assertEqual(found["y"], 5)

    def test_camp_node_appears_in_snapshot_with_expected_fields(self):
        config = SimulationConfig(
            days=5, seed=10, num_households=1, members_per_household=1,
            grid_width=12, grid_height=10,
        )
        engine = SpatialPrototypeEngine(config=config)
        camp = make_camp_node("camp-1", x=3, y=7)
        engine.nodes.append(camp)
        snapshot = engine.snapshot()
        camp_node = next(n for n in snapshot["nodes"] if n["id"] == "camp-1")
        self.assertEqual(camp_node["kind"], "camp")
        self.assertEqual(camp_node["type"], "place")
        self.assertEqual(camp_node["stock"], 0.0)
        self.assertEqual(camp_node["capacity"], CAMP_CAPACITY)
        self.assertAlmostEqual(camp_node["stock_ratio"], 0.0)
        self.assertEqual(camp_node["color"], CAMP_COLOR)
        self.assertEqual(camp_node["shelter_quality"], CAMP_SHELTER_QUALITY_DEFAULT)

    def test_make_camp_node_defaults_shelter_quality_to_zero(self):
        camp = make_camp_node("default-camp", x=2, y=3)
        self.assertEqual(camp.shelter_quality, CAMP_SHELTER_QUALITY_DEFAULT)
        self.assertEqual(camp.shelter_quality, 0.0)

    def test_make_camp_node_accepts_custom_shelter_quality(self):
        camp = make_camp_node("upgraded-camp", x=4, y=6, shelter_quality=0.4)
        self.assertEqual(camp.shelter_quality, 0.4)
        config = SimulationConfig(
            days=5, seed=10, num_households=1, members_per_household=1,
            grid_width=12, grid_height=10,
        )
        engine = SpatialPrototypeEngine(config=config)
        engine.nodes.append(camp)
        snapshot = engine.snapshot()
        camp_node = next(n for n in snapshot["nodes"] if n["id"] == "upgraded-camp")
        self.assertEqual(camp_node["shelter_quality"], 0.4)

    def test_non_camp_nodes_do_not_include_shelter_quality(self):
        config = SimulationConfig(
            days=5, seed=10, num_households=1, members_per_household=1,
            grid_width=12, grid_height=10,
        )
        engine = SpatialPrototypeEngine(config=config)
        for node in engine.nodes:
            d = node.as_dict()
            self.assertNotIn("shelter_quality", d,
                f"shelter_quality should not appear in {node.kind} node {node.id}")

    def test_camp_node_does_not_change_headless_behavior(self):
        config = SimulationConfig(
            days=5, seed=42, num_households=1, members_per_household=2,
            grid_width=12, grid_height=10,
        )
        baseline = SpatialPrototypeEngine(config=config)
        for _ in range(5):
            baseline.step()
        baseline_metrics = (
            baseline.time_series["population"][-1],
            baseline.time_series["avg_hunger"][-1],
            baseline.time_series["food_stock"][-1],
            baseline.time_series["water_stock"][-1],
        )
        engine = SpatialPrototypeEngine(config=config)
        engine.nodes.append(make_camp_node("camp-1", x=3, y=7))
        for _ in range(5):
            engine.step()
        camp_metrics = (
            engine.time_series["population"][-1],
            engine.time_series["avg_hunger"][-1],
            engine.time_series["food_stock"][-1],
            engine.time_series["water_stock"][-1],
        )
        self.assertEqual(baseline_metrics, camp_metrics)

    def test_camp_kind_is_safe_in_render_path(self):
        from view.panels import Panels
        config = SimulationConfig(
            days=5, seed=10, num_households=1, members_per_household=1,
            grid_width=12, grid_height=10,
        )
        engine = SpatialPrototypeEngine(config=config)
        camp = make_camp_node("camp-1", x=5, y=5)
        engine.nodes.append(camp)
        snapshot = engine.snapshot()
        panels = Panels(x=0, width=200, height=400)
        lines = panels._selected_lines(snapshot, ("node", "camp-1"))
        text = " ".join(lines)
        self.assertIn("camp-1", text)
        self.assertIn("camp", text)
        self.assertIn("place", text)


if __name__ == "__main__":
    unittest.main()
