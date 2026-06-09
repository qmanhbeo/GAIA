from __future__ import annotations

import importlib
import subprocess
import sys
import unittest

from gaia_config import DEFAULT_LAYOUT, DEFAULT_VIEWER_SPEED, SPATIAL_MODE, SimulationConfig
from main import run_simulation_artifact
from spatial_live_service import SpatialLiveSession
from spatial_simulation import SpatialPrototypeEngine


class MainEntrypointTests(unittest.TestCase):
    def test_headless_main_smoke_run(self):
        result = subprocess.run(
            [
                sys.executable,
                "main.py",
                "--headless",
                "--days",
                "5",
                "--households",
                "1",
                "--members",
                "2",
                "--grid-width",
                "10",
                "--grid-height",
                "8",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("Ran spatial GAIA headless for 5 ticks", result.stdout)

    def test_pygame_viewer_imports_without_starting_loop(self):
        module = importlib.import_module("view.pygame_app")
        self.assertTrue(hasattr(module, "run_pygame_app"))


class SpatialConfigTests(unittest.TestCase):
    def test_config_round_trip_without_legacy_assumptions(self):
        config = SimulationConfig(
            days=12,
            seed=99,
            num_households=3,
            members_per_household=4,
            snapshot_frequency=6,
            grid_width=18,
            grid_height=11,
        )
        rebuilt = SimulationConfig.from_dict(config.to_dict())
        self.assertEqual(config, rebuilt)
        self.assertNotIn("assumptions", rebuilt.to_dict())
        self.assertEqual(rebuilt.mode, SPATIAL_MODE)
        self.assertEqual(rebuilt.layout, DEFAULT_LAYOUT)

    def test_viewer_default_speed_is_calm(self):
        self.assertEqual(DEFAULT_VIEWER_SPEED, 2.0)


class SpatialEngineTests(unittest.TestCase):
    def test_default_layout_positions_are_inside_default_grid(self):
        config = SimulationConfig()
        engine = SpatialPrototypeEngine(config=config)
        nodes = {node.kind: node for node in engine.nodes if node.kind in {"food", "water"}}
        home = next(node for node in engine.nodes if node.kind == "home")

        self.assertEqual((home.x, home.y), (2, 8))
        self.assertEqual((nodes["food"].x, nodes["food"].y), (12, 5))
        self.assertEqual((nodes["water"].x, nodes["water"].y), (20, 10))
        for node in [home, *nodes.values()]:
            self.assertGreaterEqual(node.x, 0)
            self.assertGreaterEqual(node.y, 0)
            self.assertLess(node.x, config.grid_width)
            self.assertLess(node.y, config.grid_height)

    def test_default_layout_clamps_into_smaller_custom_grid(self):
        config = SimulationConfig(
            days=4,
            seed=6,
            num_households=3,
            members_per_household=1,
            grid_width=6,
            grid_height=4,
        )
        engine = SpatialPrototypeEngine(config=config)

        for node in engine.nodes:
            self.assertGreaterEqual(node.x, 0)
            self.assertGreaterEqual(node.y, 0)
            self.assertLess(node.x, config.grid_width)
            self.assertLess(node.y, config.grid_height)

    def test_spatial_engine_is_deterministic(self):
        config = SimulationConfig(
            days=10,
            seed=21,
            num_households=2,
            members_per_household=2,
            grid_width=14,
            grid_height=10,
        )
        first = run_simulation_artifact(config=config).to_dict()
        second = run_simulation_artifact(config=config).to_dict()
        self.assertEqual(first, second)

    def test_spatial_snapshot_has_map_and_stat_fields(self):
        engine = SpatialPrototypeEngine(
            config=SimulationConfig(
                days=6,
                seed=5,
                num_households=1,
                members_per_household=2,
                grid_width=12,
                grid_height=9,
            )
        )

        snapshot = engine.snapshot()
        required = {
            "tick",
            "clock",
            "population",
            "food_stock",
            "food_node_stock",
            "total_home_food",
            "home_storage_capacity",
            "water_stock",
            "avg_hunger",
            "avg_thirst",
            "agents",
            "nodes",
            "tiles",
            "events",
        }
        self.assertTrue(required.issubset(snapshot))
        self.assertEqual(snapshot["clock"]["tick_duration"], "1 hour")
        self.assertEqual(len(snapshot["tiles"]), 12 * 9)
        self.assertEqual(snapshot["tiles"], snapshot["grid"]["tiles"])
        self.assertEqual(snapshot["population"], snapshot["metrics"]["population"])
        self.assertEqual(snapshot["total_home_food"], snapshot["metrics"]["total_home_food"])
        self.assertEqual(snapshot["home_storage_capacity"], snapshot["metrics"]["home_storage_capacity"])
        self.assertTrue(
            all(
                "id" in agent
                and "type" in agent
                and "position" in agent
                and "home_id" in agent
                and "carried_food" in agent
                and "carry_capacity" in agent
                for agent in snapshot["agents"]
            )
        )
        self.assertTrue(all("id" in node and "type" in node and "position" in node for node in snapshot["nodes"]))
        self.assertTrue(
            all(
                "stored_food" in node and "stored_food_capacity" in node
                for node in snapshot["nodes"]
                if node["kind"] == "home"
            )
        )

    def test_agent_can_gather_food_from_node(self):
        engine = SpatialPrototypeEngine(
            config=SimulationConfig(
                days=4,
                seed=30,
                num_households=1,
                members_per_household=1,
                grid_width=12,
                grid_height=10,
            )
        )
        agent = engine.agents[0]
        food = engine._node_by_kind("food")
        home = engine._home_for_agent(agent)
        food.replenish_per_tick = 0.0
        home.stock = 0.0
        agent.x = food.x
        agent.y = food.y
        agent.hunger = 0.1
        agent.thirst = 0.1

        initial_food = food.stock
        engine.step()

        self.assertEqual(agent.last_action, "gather_food")
        self.assertEqual(agent.state, "gathering_food")
        self.assertGreater(agent.carried_food, 0.0)
        self.assertLess(food.stock, initial_food)

    def test_agent_can_carry_food_home(self):
        engine = SpatialPrototypeEngine(
            config=SimulationConfig(
                days=4,
                seed=31,
                num_households=1,
                members_per_household=1,
                grid_width=8,
                grid_height=10,
            )
        )
        agent = engine.agents[0]
        food = engine._node_by_kind("food")
        home = engine._home_for_agent(agent)
        agent.x = food.x
        agent.y = food.y
        agent.carried_food = 1.0
        agent.hunger = 0.1
        agent.thirst = 0.1
        initial_distance = abs(agent.x - home.x) + abs(agent.y - home.y)

        engine.step()
        next_distance = abs(agent.x - home.x) + abs(agent.y - home.y)

        self.assertEqual(agent.state, "carrying_food_home")
        self.assertEqual(agent.target_id, home.id)
        self.assertLess(next_distance, initial_distance)

    def test_depositing_increases_home_stored_food(self):
        engine = SpatialPrototypeEngine(
            config=SimulationConfig(
                days=4,
                seed=32,
                num_households=1,
                members_per_household=1,
                grid_width=12,
                grid_height=10,
            )
        )
        agent = engine.agents[0]
        home = engine._home_for_agent(agent)
        agent.x = home.x
        agent.y = home.y
        agent.carried_food = 1.0
        agent.hunger = 0.1
        agent.thirst = 0.1
        initial_home_food = home.stock

        engine.step()

        self.assertEqual(agent.last_action, "deposit_food")
        self.assertEqual(agent.state, "depositing_food")
        self.assertAlmostEqual(agent.carried_food, 0.0)
        self.assertGreater(home.stock, initial_home_food)

    def test_eating_from_home_storage_reduces_hunger_and_storage(self):
        engine = SpatialPrototypeEngine(
            config=SimulationConfig(
                days=4,
                seed=33,
                num_households=1,
                members_per_household=1,
                grid_width=12,
                grid_height=10,
            )
        )
        agent = engine.agents[0]
        home = engine._home_for_agent(agent)
        agent.x = home.x
        agent.y = home.y
        agent.carried_food = 0.0
        agent.hunger = 0.7
        agent.thirst = 0.1
        initial_hunger = agent.hunger
        initial_home_food = home.stock

        engine.step()

        self.assertEqual(agent.last_action, "eat_at_home")
        self.assertEqual(agent.state, "eating_at_home")
        self.assertLess(agent.hunger, initial_hunger)
        self.assertLess(home.stock, initial_home_food)

    def test_spatial_pathfinding_routes_agents_through_gap(self):
        engine = SpatialPrototypeEngine(
            config=SimulationConfig(
                days=16,
                seed=8,
                num_households=1,
                members_per_household=1,
                grid_width=24,
                grid_height=16,
            )
        )

        barrier_x = engine._barrier_x()
        gap_y = engine._gap_y()
        agent = engine.agents[0]
        agent.thirst = 0.9
        agent.hunger = 0.1

        positions = []
        for _ in range(12):
            engine.step()
            positions.append((agent.x, agent.y))

        crossed = [position for position in positions if position[0] > barrier_x]
        self.assertTrue(crossed)
        self.assertEqual(crossed[0][1], gap_y)
        self.assertTrue(all(not (x == barrier_x and y != gap_y) for x, y in positions))

    def test_spatial_consumption_requires_arrival_before_stock_changes(self):
        engine = SpatialPrototypeEngine(
            config=SimulationConfig(
                days=6,
                seed=10,
                num_households=1,
                members_per_household=1,
                grid_width=12,
                grid_height=10,
            )
        )

        agent = engine.agents[0]
        food = engine._node_by_kind("food")
        home = engine._home_for_agent(agent)
        home.stock = 0.0
        food.replenish_per_tick = 0.0
        agent.x = food.x - 1
        agent.y = food.y
        agent.hunger = 0.95
        agent.thirst = 0.1

        initial_stock = food.stock
        engine.step()
        self.assertEqual((agent.x, agent.y), (food.x, food.y))
        self.assertEqual(food.stock, initial_stock)

        engine.step()
        self.assertLess(food.stock, initial_stock)
        self.assertEqual(agent.last_action, "eat_at_node")

    def test_spatial_live_session_steps_and_resets(self):
        session = SpatialLiveSession(
            config=SimulationConfig(
                days=20,
                seed=4,
                num_households=1,
                members_per_household=3,
                grid_width=10,
                grid_height=8,
            )
        )

        initial = session.current_state()
        self.assertEqual(initial["snapshot"]["tick"], 0)

        advanced = session.step(steps=4)
        self.assertEqual(advanced["snapshot"]["tick"], 4)
        self.assertEqual(advanced["metadata"]["mode"], SPATIAL_MODE)

        reset = session.reset({"seed": 9, "grid_width": 12})
        self.assertEqual(reset["snapshot"]["tick"], 0)
        self.assertEqual(reset["metadata"]["config"]["seed"], 9)
        self.assertEqual(reset["metadata"]["config"]["grid_width"], 12)


if __name__ == "__main__":
    unittest.main()
