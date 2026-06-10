from __future__ import annotations

import importlib
import subprocess
import sys
import unittest

from analysis.audit_survival_budget import audit_config, compute_agent_budget, project_death_tick
from gaia_config import DEFAULT_LAYOUT, DEFAULT_VIEWER_SPEED, SPATIAL_MODE, SimulationConfig
from main import run_simulation_artifact
from spatial_live_service import SpatialLiveSession
from spatial_simulation import (
    HOME_MEAL_SIZE,
    HUNGER_HOME_THRESHOLD,
    THIRST_WATER_THRESHOLD,
    SpatialPrototypeEngine,
)
from rules.decision import DecisionRule
from rules.resources import ResourceRule


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


class DecisionRuleTests(unittest.TestCase):
    def setUp(self):
        self.config = SimulationConfig(
            days=5,
            seed=10,
            num_households=1,
            members_per_household=1,
            grid_width=12,
            grid_height=10,
        )
        self.engine = SpatialPrototypeEngine(config=self.config)
        self.agent = self.engine.agents[0]
        self.home = self.engine._home_for_agent(self.agent)
        self.food = self.engine._node_by_kind("food")
        self.water = self.engine._node_by_kind("water")

    def test_plan_carrying_food_returns_home(self):
        self.agent.carried_food = 0.5
        target, state = self.engine.decision_rule.choose_plan(self.engine, self.agent)
        self.assertEqual(target.kind, "home")
        self.assertEqual(state, "carrying_food_home")

    def test_plan_hungry_with_home_food_seeks_home(self):
        self.home.stock = 1.0
        self.agent.hunger = HUNGER_HOME_THRESHOLD + 0.1
        self.agent.thirst = 0.0
        target, state = self.engine.decision_rule.choose_plan(self.engine, self.agent)
        self.assertEqual(target.kind, "home")
        self.assertEqual(state, "seeking_home_food")

    def test_plan_hungry_no_home_food_seeks_food_node(self):
        self.home.stock = 0.0
        self.agent.hunger = HUNGER_HOME_THRESHOLD + 0.1
        self.agent.thirst = 0.0
        target, state = self.engine.decision_rule.choose_plan(self.engine, self.agent)
        self.assertEqual(target.kind, "food")
        self.assertEqual(state, "seeking_food")

    def test_plan_thirsty_seeks_water(self):
        self.agent.hunger = 0.0
        self.agent.thirst = THIRST_WATER_THRESHOLD + 0.1
        target, state = self.engine.decision_rule.choose_plan(self.engine, self.agent)
        self.assertEqual(target.kind, "water")
        self.assertEqual(state, "seeking_water")

    def test_plan_home_below_capacity_seeks_food(self):
        self.home.stock = 0.0
        self.agent.hunger = 0.0
        self.agent.thirst = 0.0
        self.agent.carried_food = 0.0
        target, state = self.engine.decision_rule.choose_plan(self.engine, self.agent)
        self.assertEqual(target.kind, "food")
        self.assertEqual(state, "seeking_food")

    def test_plan_resting_returns_home(self):
        self.home.stock = self.home.capacity
        self.agent.hunger = 0.0
        self.agent.thirst = 0.0
        self.agent.carried_food = 0.0
        target, state = self.engine.decision_rule.choose_plan(self.engine, self.agent)
        self.assertEqual(target.kind, "home")
        self.assertEqual(state, "resting")

    def test_plan_uses_engine_thresholds_not_hardcoded(self):
        rule = self.engine.decision_rule
        self.assertEqual(rule.hunger_home_threshold, HUNGER_HOME_THRESHOLD)
        self.assertEqual(rule.home_meal_size, HOME_MEAL_SIZE)
        self.assertEqual(rule.thirst_water_threshold, THIRST_WATER_THRESHOLD)


class ResourceRuleTests(unittest.TestCase):
    def test_replenish_nodes_without_exceeding_capacity(self):
        config = SimulationConfig(
            days=3,
            seed=1,
            num_households=1,
            members_per_household=1,
            grid_width=8,
            grid_height=6,
        )
        engine = SpatialPrototypeEngine(config=config)
        for node in engine.nodes:
            node.stock = 0.0
            node.replenish_per_tick = 0.5
        rule = ResourceRule()
        rule.apply(engine)
        for node in engine.nodes:
            self.assertGreater(node.stock, 0.0)
            self.assertLessEqual(node.stock, node.capacity)

    def test_replenish_zero_rate_does_not_change_stock(self):
        config = SimulationConfig(
            days=3,
            seed=2,
            num_households=1,
            members_per_household=1,
            grid_width=8,
            grid_height=6,
        )
        engine = SpatialPrototypeEngine(config=config)
        for node in engine.nodes:
            node.stock = 1.23
            node.replenish_per_tick = 0.0
        rule = ResourceRule()
        rule.apply(engine)
        for node in engine.nodes:
            self.assertEqual(node.stock, 1.23)


class RuleIntegrationTests(unittest.TestCase):
    def test_engine_has_decision_and_resource_rules(self):
        config = SimulationConfig(
            days=4,
            seed=7,
            num_households=1,
            members_per_household=1,
            grid_width=8,
            grid_height=6,
        )
        engine = SpatialPrototypeEngine(config=config)
        self.assertIsInstance(engine.decision_rule, DecisionRule)
        self.assertIsInstance(engine.resource_rule, ResourceRule)
        self.assertGreater(engine.decision_rule.hunger_home_threshold, 0.0)


class EventLogTests(unittest.TestCase):
    def test_gather_food_records_event(self):
        engine = SpatialPrototypeEngine(
            config=SimulationConfig(
                days=4, seed=30, num_households=1, members_per_household=1, grid_width=12, grid_height=10,
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
        engine.step()
        self.assertIn("gather_food", [e["event"] for e in engine.events])

    def test_deposit_food_records_event(self):
        engine = SpatialPrototypeEngine(
            config=SimulationConfig(
                days=4, seed=31, num_households=1, members_per_household=1, grid_width=8, grid_height=6,
            )
        )
        agent = engine.agents[0]
        home = engine._home_for_agent(agent)
        agent.x = home.x
        agent.y = home.y
        agent.carried_food = 0.5
        home.stock = 0.0
        engine.step()
        self.assertIn("deposit_food", [e["event"] for e in engine.events])

    def test_eat_at_home_records_event(self):
        engine = SpatialPrototypeEngine(
            config=SimulationConfig(
                days=4, seed=32, num_households=1, members_per_household=1, grid_width=8, grid_height=6,
            )
        )
        agent = engine.agents[0]
        home = engine._home_for_agent(agent)
        agent.x = home.x
        agent.y = home.y
        agent.carried_food = 0.0
        agent.hunger = 0.6
        home.stock = 5.0
        engine.step()
        self.assertIn("eat_at_home", [e["event"] for e in engine.events])

    def test_drink_records_event(self):
        engine = SpatialPrototypeEngine(
            config=SimulationConfig(
                days=4, seed=33, num_households=1, members_per_household=1, grid_width=8, grid_height=6,
            )
        )
        agent = engine.agents[0]
        water = engine._node_by_kind("water")
        agent.x = water.x
        agent.y = water.y
        agent.carried_food = 0.0
        agent.hunger = 0.1
        agent.thirst = 0.9
        engine.step()
        self.assertIn("drink", [e["event"] for e in engine.events])

    def test_snapshot_events_match_current_tick(self):
        engine = SpatialPrototypeEngine(
            config=SimulationConfig(
                days=4, seed=5, num_households=1, members_per_household=1, grid_width=8, grid_height=6,
            )
        )
        for _ in range(3):
            snapshot = engine.step()
            for entry in snapshot["events"]:
                self.assertEqual(entry["tick"], snapshot["tick"])

    def test_event_log_is_deterministic(self):
        config = SimulationConfig(
            days=4, seed=42, num_households=1, members_per_household=1, grid_width=8, grid_height=6,
        )
        first = SpatialPrototypeEngine(config=config)
        second = SpatialPrototypeEngine(config=config)
        for _ in range(5):
            first.step()
            second.step()
        self.assertEqual(first.event_log, second.event_log)


class HomeostaticCommitmentTests(unittest.TestCase):
    def test_seeking_water_ignores_mild_hunger(self):
        engine = SpatialPrototypeEngine(
            config=SimulationConfig(
                days=4, seed=10, num_households=1, members_per_household=1, grid_width=12, grid_height=10,
            )
        )
        agent = engine.agents[0]
        water = engine._node_by_kind("water")
        agent.current_task = "seek_water"
        agent.task_target_id = water.id
        agent.hunger = 0.6
        agent.thirst = 0.9
        target, state = engine.decision_rule.choose_plan(engine, agent)
        self.assertEqual(target.kind, "water")

    def test_seeking_food_ignores_mild_thirst(self):
        engine = SpatialPrototypeEngine(
            config=SimulationConfig(
                days=4, seed=10, num_households=1, members_per_household=1, grid_width=12, grid_height=10,
            )
        )
        agent = engine.agents[0]
        food = engine._node_by_kind("food")
        agent.current_task = "seek_food"
        agent.task_target_id = food.id
        agent.hunger = 0.7
        agent.thirst = 0.85
        target, state = engine.decision_rule.choose_plan(engine, agent)
        self.assertEqual(target.kind, "food")

    def test_seeking_food_overrides_when_thirst_critical(self):
        engine = SpatialPrototypeEngine(
            config=SimulationConfig(
                days=4, seed=10, num_households=1, members_per_household=1, grid_width=12, grid_height=10,
            )
        )
        agent = engine.agents[0]
        food = engine._node_by_kind("food")
        agent.current_task = "seek_food"
        agent.task_target_id = food.id
        agent.hunger = 0.7
        agent.thirst = 0.95
        engine.decision_rule.choose_plan(engine, agent)
        self.assertEqual(agent.current_task, "seek_water")

    def test_gather_food_sets_return_home_task(self):
        engine = SpatialPrototypeEngine(
            config=SimulationConfig(
                days=4, seed=30, num_households=1, members_per_household=1, grid_width=12, grid_height=10,
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
        engine.step()
        self.assertGreater(agent.carried_food, 0.0)
        self.assertEqual(agent.current_task, "return_home_with_food")
        self.assertEqual(agent.task_target_id, home.id)

    def test_deposit_food_clears_task(self):
        engine = SpatialPrototypeEngine(
            config=SimulationConfig(
                days=4, seed=31, num_households=1, members_per_household=1, grid_width=8, grid_height=6,
            )
        )
        agent = engine.agents[0]
        home = engine._home_for_agent(agent)
        agent.x = home.x
        agent.y = home.y
        agent.carried_food = 0.5
        engine.step()
        self.assertEqual(agent.last_action, "deposit_food")
        self.assertIsNone(agent.current_task)
        self.assertIsNone(agent.task_target_id)

    def test_drink_clears_task(self):
        engine = SpatialPrototypeEngine(
            config=SimulationConfig(
                days=4, seed=31, num_households=1, members_per_household=1, grid_width=8, grid_height=6,
            )
        )
        agent = engine.agents[0]
        water = engine._node_by_kind("water")
        agent.x = water.x
        agent.y = water.y
        agent.hunger = 0.1
        agent.thirst = 0.9
        engine.step()
        self.assertEqual(agent.last_action, "drink")
        self.assertIsNone(agent.current_task)
        self.assertIsNone(agent.task_target_id)


class HomeostaticAuditTests(unittest.TestCase):
    def _run_engine(self):
        config = SimulationConfig(
            days=200, seed=42, num_households=2, members_per_household=2, grid_width=12, grid_height=10,
        )
        engine = SpatialPrototypeEngine(config=config)
        for _ in range(200):
            engine.step()
        return engine

    def test_medium_run_produces_drink_event(self):
        engine = self._run_engine()
        self.assertTrue(any(e["event"] == "drink" for e in engine.event_log))

    def test_medium_run_decreases_water_stock(self):
        engine = self._run_engine()
        min_stock = min(engine.time_series["water_stock"])
        self.assertLess(min_stock, 8.0)

    def test_agents_do_not_all_die_with_water_untouched(self):
        engine = self._run_engine()
        pop = engine.time_series["population"][-1]
        water_used = any(e["event"] == "drink" for e in engine.event_log)
        self.assertTrue(pop > 0 or water_used)


class SurvivalBudgetTests(unittest.TestCase):
    def test_compute_agent_budget_returns_finite_distances(self):
        config = SimulationConfig(
            days=2, seed=1, num_households=1, members_per_household=1,
            grid_width=12, grid_height=10,
        )
        engine = SpatialPrototypeEngine(config=config)
        agent = engine.agents[0]
        budget = compute_agent_budget(engine, agent)
        self.assertIsNotNone(budget["distance_to_home"])
        self.assertIsNotNone(budget["distance_to_food"])
        self.assertIsNotNone(budget["distance_to_water"])
        self.assertGreater(budget["distance_to_food"], 0)
        self.assertGreater(budget["distance_to_water"], 0)

    def test_budget_time_to_critical_decreases_with_higher_needs(self):
        config = SimulationConfig(
            days=2, seed=1, num_households=1, members_per_household=1,
            grid_width=12, grid_height=10,
        )
        engine = SpatialPrototypeEngine(config=config)
        agent = engine.agents[0]
        agent.hunger = 0.3
        agent.thirst = 0.3
        budget_low = compute_agent_budget(engine, agent)
        agent.hunger = 0.7
        agent.thirst = 0.7
        budget_high = compute_agent_budget(engine, agent)
        self.assertGreater(
            budget_low["ticks_until_hunger_critical"],
            budget_high["ticks_until_hunger_critical"],
        )
        self.assertGreater(
            budget_low["ticks_until_thirst_critical"],
            budget_high["ticks_until_thirst_critical"],
        )

    def test_nearby_target_marked_more_survivable(self):
        config = SimulationConfig(
            days=2, seed=1, num_households=1, members_per_household=2,
            grid_width=12, grid_height=10,
        )
        engine = SpatialPrototypeEngine(config=config)
        agent_near = engine.agents[0]
        agent_far = engine.agents[1]
        water = engine._node_by_kind("water")
        agent_near.x = water.x
        agent_near.y = water.y
        budget_near = compute_agent_budget(engine, agent_near)
        budget_far = compute_agent_budget(engine, agent_far)
        self.assertEqual(budget_near["distance_to_water"], 0)
        self.assertGreater(budget_far["distance_to_water"], budget_near["distance_to_water"])

    def test_project_death_tick_decreases_with_higher_needs(self):
        low = project_death_tick(0.3, 0.3, 1.0)
        high = project_death_tick(0.7, 0.7, 1.0)
        self.assertGreater(low, high)

    def test_audit_imports_and_runs_without_mutation(self):
        config = SimulationConfig(
            days=2, seed=5, num_households=1, members_per_household=1,
            grid_width=12, grid_height=10,
        )
        results = audit_config(config)
        self.assertIn("final_population", results)
        self.assertIn("initial_budgets", results)
        self.assertEqual(len(results["initial_budgets"]), 1)


if __name__ == "__main__":
    unittest.main()
