from __future__ import annotations

import importlib
import subprocess
import sys
import unittest
from unittest.mock import patch

from analysis.audit_survival_budget import audit_config, compute_agent_budget, project_death_tick
from analysis.calibrate_survival_budget import run_sweep
from gaia_config import DEFAULT_LAYOUT, DEFAULT_VIEWER_SPEED, SPATIAL_MODE, PhysiologyConfig, SimulationConfig
from main import run_simulation_artifact
from spatial_live_service import SpatialLiveSession
from spatial_simulation import (
    HOME_MEAL_SIZE,
    HUNGER_HOME_THRESHOLD,
    THIRST_WATER_THRESHOLD,
    CAMP_CAPACITY,
    CAMP_COLOR,
    CAMP_SHELTER_QUALITY_DEFAULT,
    SpatialPrototypeEngine,
    make_camp_node,
)
from rules.decision import DecisionRule, NeedSpec, SatisfierSpec
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


class PhysiologyConfigTests(unittest.TestCase):
    def test_physiology_defaults_match_hardcoded(self):
        phys = PhysiologyConfig()
        self.assertEqual(phys.hunger_increase_per_tick, 0.032)
        self.assertEqual(phys.thirst_increase_per_tick, 0.041)
        self.assertEqual(phys.hunger_damage_threshold, 0.88)
        self.assertEqual(phys.thirst_damage_threshold, 0.91)
        self.assertEqual(phys.hunger_damage_rate, 0.016)
        self.assertEqual(phys.thirst_damage_rate, 0.022)
        self.assertEqual(phys.home_health_regen_per_tick, 0.012)

    def test_physiology_from_dict_fails_on_bad_field(self):
        with self.assertRaises(TypeError):
            PhysiologyConfig(hunger_increase_per_tick=0.02, nonexistent_field=0.5)

    def test_default_simulation_behavior_unchanged(self):
        config = SimulationConfig(
            days=5, seed=42, num_households=1, members_per_household=2,
            grid_width=12, grid_height=10,
        )
        engine = SpatialPrototypeEngine(config=config)
        for _ in range(5):
            engine.step()
        pop = engine.time_series["population"]
        self.assertGreater(pop[-1], 0)
        self.assertGreater(engine.time_series["avg_hunger"][-1], 0.3)

    def test_decision_rule_thresholds_from_physiology(self):
        config = SimulationConfig()
        engine = SpatialPrototypeEngine(config=config)
        phys = config.physiology
        self.assertEqual(engine.decision_rule.hunger_critical, phys.hunger_damage_threshold)
        self.assertEqual(engine.decision_rule.thirst_critical, phys.thirst_damage_threshold)

    def test_audit_uses_config_physiology(self):
        config = SimulationConfig(
            days=2, seed=1, num_households=1, members_per_household=1,
            grid_width=12, grid_height=10,
        )
        results = audit_config(config)
        self.assertIn("physiology", results)
        phys = results["physiology"]
        self.assertEqual(phys["hunger_increase_per_tick"], 0.032)
        self.assertEqual(phys["thirst_increase_per_tick"], 0.041)

    def test_calibrate_imports_and_runs_tiny_sweep(self):
        results = run_sweep(
            days=2, num_households=1, members_per_household=1,
            grid_width=12, grid_height=10,
        )
        self.assertGreater(len(results), 0)
        self.assertIn("score", results[0])
        self.assertIn("final_population", results[0])


class DepletableResourceTests(unittest.TestCase):
    def setUp(self):
        self.config = SimulationConfig(
            days=5, seed=10, num_households=1, members_per_household=1,
            grid_width=12, grid_height=10,
        )
        self.engine = SpatialPrototypeEngine(config=self.config)
        self.agent = self.engine.agents[0]
        self.home = self.engine._home_for_agent(self.agent)
        self.food = self.engine._node_by_kind("food")
        self.water = self.engine._node_by_kind("water")

    def test_drinking_reduces_water_stock(self):
        self.agent.x = self.water.x
        self.agent.y = self.water.y
        self.agent.thirst = 0.95
        self.agent.hunger = 0.0
        initial = self.water.stock
        self.engine.step()
        self.assertIn("drink", [e["event"] for e in self.engine.events])
        self.assertLess(self.water.stock, initial)

    def test_resource_regenerates_up_to_capacity(self):
        self.water.stock = 0.0
        for _ in range(50):
            self.engine.resource_rule.apply(self.engine)
        self.assertEqual(self.water.stock, self.water.capacity)

    def test_hungry_agent_avoids_depleted_food_when_home_has_food(self):
        self.food.stock = 0.0
        self.home.stock = 1.0
        self.agent.hunger = 0.6
        self.agent.thirst = 0.0
        target, state = self.engine.decision_rule.choose_plan(self.engine, self.agent)
        self.assertEqual(target.kind, "home")

    def test_committed_seek_food_abandoned_when_target_depleted(self):
        from spatial_simulation import SpatialNode
        second_food = SpatialNode(
            id="food-2", kind="food", label="Second Field",
            x=6, y=8,
            stock=5.0, capacity=7.0, replenish_per_tick=0.18,
            color="#9df584",
        )
        self.engine.nodes.append(second_food)
        self.agent.current_task = "seek_food"
        self.agent.task_target_id = self.food.id
        self.food.stock = 0.0
        self.home.stock = 0.0
        self.agent.hunger = 0.6
        self.agent.thirst = 0.0
        target, state = self.engine.decision_rule.choose_plan(self.engine, self.agent)
        self.assertEqual(target.id, second_food.id)
        self.assertEqual(state, "seeking_food")

    def test_committed_target_preserved_across_ticks(self):
        from spatial_simulation import SpatialNode
        second_food = SpatialNode(
            id="food-2", kind="food", label="Second Field",
            x=6, y=8,
            stock=5.0, capacity=7.0, replenish_per_tick=0.18,
            color="#9df584",
        )
        self.engine.nodes.append(second_food)
        self.food.stock = 0.0
        self.home.stock = 0.0
        self.agent.hunger = 0.6
        self.agent.thirst = 0.0
        target1, _ = self.engine.decision_rule.choose_plan(self.engine, self.agent)
        self.assertEqual(target1.id, second_food.id)
        self.assertEqual(self.agent.task_target_id, "food-2")
        target2, _ = self.engine.decision_rule.choose_plan(self.engine, self.agent)
        self.assertEqual(target2.id, second_food.id)

    def test_estimate_death_time_respects_physiology_thresholds(self):
        from gaia_config import PhysiologyConfig
        phys_default = PhysiologyConfig()
        phys_low = PhysiologyConfig(
            hunger_damage_threshold=0.5, thirst_damage_threshold=0.5,
        )
        agent = self.agent
        dt_default = self.engine.decision_rule._estimate_death_time(agent, phys_default)
        dt_low = self.engine.decision_rule._estimate_death_time(agent, phys_low)
        self.assertGreater(dt_default, dt_low,
            "lower damage thresholds should give shorter death projection")

    def test_agent_chooses_viable_food_over_depleted_food(self):
        from spatial_simulation import SpatialNode
        second_food = SpatialNode(
            id="food-2", kind="food", label="Second Field",
            x=6, y=8,
            stock=5.0, capacity=7.0, replenish_per_tick=0.18,
            color="#9df584",
        )
        self.engine.nodes.append(second_food)
        self.food.stock = 0.0
        self.home.stock = 0.0
        self.agent.hunger = 0.6
        self.agent.thirst = 0.0
        target, state = self.engine.decision_rule.choose_plan(self.engine, self.agent)
        self.assertEqual(target.id, second_food.id)
        self.assertEqual(state, "seeking_food")
        path = self.engine._find_path((self.agent.x, self.agent.y), (target.x, target.y), {})
        self.assertIsNotNone(path)


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


class NodeMemoryTests(unittest.TestCase):
    def setUp(self):
        self.config = SimulationConfig(
            days=5, seed=10, num_households=1, members_per_household=1,
            grid_width=12, grid_height=10,
        )
        self.engine = SpatialPrototypeEngine(config=self.config)
        self.agent = self.engine.agents[0]
        self.food = self.engine._node_by_kind("food")
        self.home = self.engine._home_for_agent(self.agent)

    def test_agent_starts_with_empty_node_memory(self):
        self.assertEqual(self.agent.node_memory, {})

    def test_agent_observes_food_node_when_standing_on_it(self):
        self.agent.x = self.food.x
        self.agent.y = self.food.y
        self.agent.hunger = 0.6
        self.agent.thirst = 0.0
        self.engine.step()
        self.assertIn(self.food.id, self.agent.node_memory)

    def test_memory_entry_has_expected_shape(self):
        self.agent.x = self.food.x
        self.agent.y = self.food.y
        self.agent.hunger = 0.6
        self.agent.thirst = 0.0
        self.engine.step()
        entry = self.agent.node_memory[self.food.id]
        self.assertIn("kind", entry)
        self.assertIn("label", entry)
        self.assertIn("x", entry)
        self.assertIn("y", entry)
        self.assertIn("last_seen_stock", entry)
        self.assertIn("last_seen_capacity", entry)
        self.assertIn("last_seen_tick", entry)
        self.assertEqual(entry["kind"], "food")
        self.assertEqual(entry["label"], self.food.label)
        self.assertEqual(entry["x"], self.food.x)
        self.assertEqual(entry["y"], self.food.y)
        self.assertIsInstance(entry["last_seen_stock"], float)
        self.assertIsInstance(entry["last_seen_capacity"], float)
        self.assertIsInstance(entry["last_seen_tick"], int)

    def test_memory_updates_last_seen_stock_on_reobservation(self):
        self.agent.x = self.food.x
        self.agent.y = self.food.y
        self.agent.hunger = 0.95
        self.agent.thirst = 0.0
        self.engine.step()
        first_entry = self.agent.node_memory[self.food.id]
        first_stock = first_entry["last_seen_stock"]
        self.assertLess(first_stock, self.food.capacity)
        self.food.stock = first_stock + 1.0
        self.engine._observe_node(self.agent, self.food, self.engine.tick)
        updated_entry = self.agent.node_memory[self.food.id]
        self.assertNotEqual(updated_entry["last_seen_stock"], first_stock)
        self.assertEqual(updated_entry["last_seen_stock"], self.food.stock)

    def test_camp_node_can_be_remembered(self):
        camp = make_camp_node("memory-camp", x=self.home.x, y=self.home.y)
        self.engine.nodes.append(camp)
        self.agent.x = self.home.x
        self.agent.y = self.home.y
        self.agent.hunger = 0.0
        self.agent.thirst = 0.0
        self.home.stock = self.home.capacity
        self.engine.step()
        self.assertIn("memory-camp", self.agent.node_memory)
        entry = self.agent.node_memory["memory-camp"]
        self.assertEqual(entry["kind"], "camp")
        self.assertEqual(entry["x"], self.home.x)
        self.assertEqual(entry["y"], self.home.y)

    def test_memory_serialized_in_agent_as_dict(self):
        self.agent.x = self.food.x
        self.agent.y = self.food.y
        self.agent.hunger = 0.6
        self.agent.thirst = 0.0
        self.engine.step()
        serialized = self.agent.as_dict()
        self.assertIn("node_memory", serialized)
        mem = serialized["node_memory"]
        self.assertIn(self.food.id, mem)
        entry = mem[self.food.id]
        self.assertIn("last_seen_stock", entry)
        self.assertIsInstance(entry["last_seen_stock"], float)
        self.assertIn("last_seen_tick", entry)
        self.assertIsInstance(entry["last_seen_tick"], int)

class NeedSpecTests(unittest.TestCase):
    def setUp(self):
        self.config = SimulationConfig(
            days=5, seed=10, num_households=1, members_per_household=1,
            grid_width=12, grid_height=10,
        )
        self.engine = SpatialPrototypeEngine(config=self.config)
        self.agent = self.engine.agents[0]
        self.home = self.engine._home_for_agent(self.agent)
        self.food = self.engine._node_by_kind("food")
        self.water = self.engine._node_by_kind("water")
        self.rule = self.engine.decision_rule

    def test_need_specs_exist_for_hunger_and_thirst(self):
        need_names = [n.name for n in self.rule.NEEDS]
        self.assertIn("hunger", need_names)
        self.assertIn("thirst", need_names)

    def test_need_spec_has_correct_thresholds(self):
        hunger = next(n for n in self.rule.NEEDS if n.name == "hunger")
        thirst = next(n for n in self.rule.NEEDS if n.name == "thirst")
        self.assertEqual(hunger.critical_threshold, self.rule.hunger_critical)
        self.assertEqual(hunger.mild_threshold, self.rule.hunger_home_threshold)
        self.assertEqual(thirst.critical_threshold, self.rule.thirst_critical)
        self.assertEqual(thirst.mild_threshold, self.rule.thirst_water_threshold)

    def test_satisfier_specs_cover_current_tasks(self):
        task_names = set()
        for satisfiers in self.rule.SATISFIERS.values():
            for sat in satisfiers:
                task_names.add(sat.task_name)
        self.assertIn("seek_food", task_names)
        self.assertIn("seek_home_food", task_names)
        self.assertIn("seek_water", task_names)
        self.assertEqual(len(task_names), 3)

    def test_candidates_for_thirst_returns_water(self):
        candidates = self.rule._candidates_for_need(self.engine, self.agent, "thirst")
        self.assertEqual(len(candidates), 1)
        node, task = candidates[0]
        self.assertEqual(node.kind, "water")
        self.assertEqual(task, "seek_water")

    def test_candidates_for_hunger_includes_food_nodes(self):
        candidates = self.rule._candidates_for_need(self.engine, self.agent, "hunger")
        food_nodes = [(n, t) for n, t in candidates if n.kind == "food"]
        self.assertGreaterEqual(len(food_nodes), 1)
        for n, t in food_nodes:
            self.assertEqual(t, "seek_food")

    def test_candidates_for_hunger_includes_home_when_stocked(self):
        self.home.stock = 1.0
        candidates = self.rule._candidates_for_need(self.engine, self.agent, "hunger")
        home_candidates = [(n, t) for n, t in candidates if n.kind == "home"]
        self.assertEqual(len(home_candidates), 1)
        self.assertEqual(home_candidates[0][1], "seek_home_food")

    def test_candidates_for_hunger_excludes_home_below_meal(self):
        self.home.stock = 0.1
        candidates = self.rule._candidates_for_need(self.engine, self.agent, "hunger")
        home_candidates = [(n, t) for n, t in candidates if n.kind == "home"]
        self.assertEqual(len(home_candidates), 0)

    def test_candidate_is_depleted_rejects_empty_food(self):
        self.food.stock = 0.0
        self.assertTrue(self.rule._candidate_is_depleted(self.food, "seek_food"))

    def test_candidate_is_depleted_accepts_stocked_food(self):
        self.food.stock = 5.0
        self.assertFalse(self.rule._candidate_is_depleted(self.food, "seek_food"))

    def test_candidate_is_depleted_rejects_empty_water(self):
        self.water.stock = 0.0
        self.assertTrue(self.rule._candidate_is_depleted(self.water, "seek_water"))

    def test_candidate_is_depleted_rejects_home_below_meal(self):
        self.home.stock = 0.1
        self.assertTrue(self.rule._candidate_is_depleted(self.home, "seek_home_food"))

    def test_candidate_is_depleted_accepts_home_at_or_above_meal(self):
        self.home.stock = 0.25
        self.assertFalse(self.rule._candidate_is_depleted(self.home, "seek_home_food"))
        self.home.stock = 0.5
        self.assertFalse(self.rule._candidate_is_depleted(self.home, "seek_home_food"))

    def test_candidate_is_depleted_false_for_non_satisfier_task(self):
        self.home.stock = 0.0
        self.assertFalse(self.rule._candidate_is_depleted(self.home, "return_home_with_food"))

    def test_candidate_is_depleted_skipped_for_non_stock_satisfier(self):
        dummy_rest = SatisfierSpec(
            need_name="fatigue", task_name="seek_rest",
            target_kind="home", is_home_satisfier=True,
            requires_stock=False,
        )
        self.rule.SATISFIERS.setdefault("fatigue", []).append(dummy_rest)
        self.home.stock = 0.0
        self.assertFalse(self.rule._candidate_is_depleted(self.home, "seek_rest"))

class MemoryTieBreakTests(unittest.TestCase):
    def setUp(self):
        self.config = SimulationConfig(
            days=5, seed=10, num_households=1, members_per_household=1,
            grid_width=12, grid_height=10,
        )
        self.engine = SpatialPrototypeEngine(config=self.config)
        self.agent = self.engine.agents[0]
        self.home = self.engine._home_for_agent(self.agent)
        self.food = self.engine._node_by_kind("food")
        self.water = self.engine._node_by_kind("water")
        self.rule = self.engine.decision_rule
        from spatial_simulation import SpatialNode
        self.second_food = SpatialNode(
            id="food-2", kind="food", label="Second Field",
            x=6, y=8,
            stock=5.0, capacity=7.0, replenish_per_tick=0.18,
            color="#9df584",
        )
        self.engine.nodes.append(self.second_food)

    def test_memory_tie_breaker_prefers_remembered(self):
        candidates = [(self.food, "seek_food"), (self.second_food, "seek_food")]
        self.agent.node_memory[self.second_food.id] = {}
        from unittest.mock import patch
        with patch.object(self.rule, '_compute_eta', return_value=5):
            best_node, best_task = self.rule._best_viable_target(self.engine, self.agent, candidates)
        self.assertEqual(best_node.id, self.second_food.id,
            "remembered node should win when slack ties")

    def test_better_slack_beats_memory(self):
        candidates = [(self.food, "seek_food"), (self.second_food, "seek_food")]
        self.agent.node_memory[self.food.id] = {}
        from unittest.mock import patch
        with patch.object(self.rule, '_compute_eta',
                          side_effect=lambda e, a, n: {self.food.id: 10, self.second_food.id: 2}.get(n.id, 100)):
            best_node, best_task = self.rule._best_viable_target(self.engine, self.agent, candidates)
        self.assertEqual(best_node.id, self.second_food.id,
            "unknown node with better slack should beat remembered node")

    def test_remembered_depleted_rejected(self):
        self.food.stock = 0.0
        self.agent.node_memory[self.food.id] = {}
        candidates = [(self.food, "seek_food"), (self.second_food, "seek_food")]
        from unittest.mock import patch
        with patch.object(self.rule, '_compute_eta', return_value=5):
            best_node, best_task = self.rule._best_viable_target(self.engine, self.agent, candidates)
        self.assertEqual(best_node.id, self.second_food.id,
            "depleted remembered node should be rejected; stocked unknown should win")

    def test_no_memory_behavior_unchanged(self):
        candidates = [(self.food, "seek_food"), (self.second_food, "seek_food")]
        from unittest.mock import patch
        with patch.object(self.rule, '_compute_eta',
                          side_effect=lambda e, a, n: {self.food.id: 5, self.second_food.id: 3}.get(n.id, 100)):
            best_node, best_task = self.rule._best_viable_target(self.engine, self.agent, candidates)
        self.assertEqual(best_node.id, self.second_food.id,
            "better slack should win when neither candidate is remembered")

    def test_node_memory_only_in_helper(self):
        import inspect
        from rules.decision import DecisionRule
        source = inspect.getsource(DecisionRule)
        count = source.count("node_memory")
        self.assertEqual(count, 1,
            "node_memory must appear exactly once in DecisionRule source "
            "(in _candidate_memory_score); found {}".format(count))

    def test_camps_not_in_candidates_for_need(self):
        config = SimulationConfig(
            days=5, seed=10, num_households=1, members_per_household=1,
            grid_width=12, grid_height=10,
        )
        engine = SpatialPrototypeEngine(config=config)
        from spatial_simulation import make_camp_node
        camp = make_camp_node("camp-test", x=3, y=7)
        engine.nodes.append(camp)
        agent = engine.agents[0]
        rule = engine.decision_rule
        for need_name in ("hunger", "thirst"):
            candidates = rule._candidates_for_need(engine, agent, need_name)
            camp_candidates = [(n, t) for n, t in candidates if n.kind == "camp"]
            self.assertEqual(len(camp_candidates), 0,
                "camps should not appear in candidates for {}".format(need_name))


class RestSafetyScaffoldTests(unittest.TestCase):
    def setUp(self):
        self.config = SimulationConfig(
            days=5, seed=10, num_households=1, members_per_household=2,
            grid_width=12, grid_height=10,
        )
        self.engine = SpatialPrototypeEngine(config=self.config)
        self.agent = self.engine.agents[0]
        self.home = self.engine._home_for_agent(self.agent)

    def test_agent_starts_with_zero_fatigue(self):
        self.assertEqual(self.agent.fatigue, 0.0)

    def test_fatigue_increases_after_one_tick(self):
        phys = self.config.physiology
        self.engine._apply_base_fatigue(self.agent)
        self.assertAlmostEqual(self.agent.fatigue, phys.fatigue_increase_per_tick, places=4)

    def test_fatigue_is_clamped_to_one(self):
        self.agent.fatigue = 0.99
        phys = self.engine.config.physiology
        self.engine.step()
        self.assertLessEqual(self.agent.fatigue, 1.0)

    def test_fatigue_serialized_in_agent_as_dict(self):
        serialized = self.agent.as_dict()
        self.assertIn("fatigue", serialized)
        self.assertIsInstance(serialized["fatigue"], float)

    def test_fatigue_in_components_needs(self):
        serialized = self.agent.as_dict()
        self.assertIn("fatigue", serialized["components"]["needs"])

    def test_home_has_rest_safety_one(self):
        self.assertEqual(self.home.rest_safety, 1.0)

    def test_default_camp_rest_safety_is_zero(self):
        from spatial_simulation import make_camp_node
        camp = make_camp_node("camp-default", x=3, y=7)
        self.assertEqual(camp.rest_safety, 0.0)

    def test_custom_camp_rest_safety_matches_shelter_quality(self):
        from spatial_simulation import make_camp_node
        camp = make_camp_node("camp-custom", x=4, y=6, shelter_quality=0.4)
        self.assertEqual(camp.rest_safety, 0.4)
        self.assertEqual(camp.rest_safety, camp.shelter_quality)

    def test_rest_safety_serialized_in_node_as_dict(self):
        serialized = self.home.as_dict()
        self.assertIn("rest_safety", serialized)
        self.assertAlmostEqual(serialized["rest_safety"], 1.0)

    def test_nearby_agents_returns_self_when_alone(self):
        self.agent.x = 0
        self.agent.y = 0
        nearby = self.engine._nearby_agents(self.agent, radius=1)
        self.assertIn(self.agent, nearby)
        self.assertEqual(len(nearby), 1)

    def test_nearby_agents_includes_other_on_same_tile(self):
        other = self.engine.agents[1]
        other.x = self.agent.x
        other.y = self.agent.y
        nearby = self.engine._nearby_agents(self.agent, radius=1)
        self.assertIn(self.agent, nearby)
        self.assertIn(other, nearby)
        self.assertEqual(len(nearby), 2)

    def test_nearby_agents_includes_adjacent_within_radius(self):
        other = self.engine.agents[1]
        other.x = self.agent.x + 1
        other.y = self.agent.y
        nearby = self.engine._nearby_agents(self.agent, radius=1)
        self.assertIn(other, nearby,
            "adjacent agent should be within radius 1")

    def test_nearby_agents_excludes_outside_radius(self):
        other = self.engine.agents[1]
        other.x = self.agent.x + 5
        other.y = self.agent.y
        nearby = self.engine._nearby_agents(self.agent, radius=1)
        self.assertNotIn(other, nearby,
            "agent at distance 5 should be excluded")

    def test_nearby_agents_excludes_dead_agents(self):
        other = self.engine.agents[1]
        other.x = self.agent.x
        other.y = self.agent.y
        other.health = 0.0
        self.assertFalse(other.is_alive())
        nearby = self.engine._nearby_agents(self.agent, radius=1)
        self.assertIn(self.agent, nearby)
        self.assertNotIn(other, nearby,
            "dead agent should be excluded from nearby_agents")


class FatigueRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.config = SimulationConfig(
            days=5, seed=10, num_households=1, members_per_household=2,
            grid_width=12, grid_height=10,
        )
        self.engine = SpatialPrototypeEngine(config=self.config)
        self.agent = self.engine.agents[0]
        self.other = self.engine.agents[1]
        self.home = self.engine._home_for_agent(self.agent)

    def _place_at_home(self, agent):
        agent.x = self.home.x
        agent.y = self.home.y
        agent.carried_food = 0.0
        agent.hunger = 0.0
        agent.thirst = 0.0

    def test_resting_at_home_reduces_fatigue(self):
        self._place_at_home(self.agent)
        self.home.stock = self.home.capacity
        self.agent.fatigue = 0.5
        phys = self.config.physiology
        self.engine.step()
        expected = max(0.0, 0.5 + phys.fatigue_increase_per_tick - phys.fatigue_recovery_per_tick)
        self.assertAlmostEqual(self.agent.fatigue, expected, places=4,
            msg="fatigue should decrease when resting at home")

    def test_fatigue_recovery_clamped_at_zero(self):
        self._place_at_home(self.agent)
        self.home.stock = self.home.capacity
        self.agent.fatigue = 0.01
        phys = self.config.physiology
        self.engine.step()
        expected = max(0.0, 0.01 + phys.fatigue_increase_per_tick - phys.fatigue_recovery_per_tick)
        self.assertAlmostEqual(self.agent.fatigue, expected, places=4,
            msg="fatigue recovery should clamp at 0.0")

    def test_self_not_counted_as_group_bonus(self):
        self._place_at_home(self.agent)
        self.home.stock = self.home.capacity
        self.agent.fatigue = 0.5
        phys = self.config.physiology
        self.engine.step()
        expected = max(0.0, 0.5 + phys.fatigue_increase_per_tick - phys.fatigue_recovery_per_tick)
        self.assertAlmostEqual(self.agent.fatigue, expected, places=4,
            msg="single agent should recover at base rate (no group bonus)")

    def test_effective_rest_quality_alone(self):
        self._place_at_home(self.agent)
        quality = self.engine._effective_rest_quality(self.agent, self.home)
        self.assertEqual(quality, 1.0,
            "home rest_safety=1.0 alone should give quality 1.0")

    def test_effective_rest_quality_with_nearby_other(self):
        home2 = self.engine._home_for_agent(self.other)
        home2.rest_safety = 0.5
        self._place_at_home(self.other)
        self.other.x = self.home.x
        self.other.y = self.home.y
        self._place_at_home(self.agent)
        quality = self.engine._effective_rest_quality(self.agent, home2)
        expected = min(1.0, 0.5 + 0.1)
        self.assertAlmostEqual(quality, expected, places=4,
            msg="nearby other should increase rest quality by group bonus")

    def test_effective_rest_quality_clamps_at_one(self):
        self._place_at_home(self.agent)
        self.other.x = self.home.x
        self.other.y = self.home.y
        self.home.rest_safety = 0.95
        quality = self.engine._effective_rest_quality(self.agent, self.home)
        self.assertEqual(quality, 1.0,
            "effective rest quality should clamp at 1.0")

    def test_hunger_eat_at_home_still_precedes_rest(self):
        self._place_at_home(self.agent)
        self.home.stock = 1.0
        self.agent.hunger = 0.6
        self.agent.fatigue = 0.5
        self.engine.step()
        self.assertEqual(self.agent.last_action, "eat_at_home",
            "hungry agent with home food should eat, not rest")

    def test_decision_rule_unchanged(self):
        import inspect
        from rules.decision import DecisionRule
        source = inspect.getsource(DecisionRule)
        self.assertIn("def choose_plan", source)
        self.assertNotIn("fatigue", source,
            "DecisionRule should not reference fatigue yet")

    def test_camps_remain_inert(self):
        from spatial_simulation import make_camp_node
        camp = make_camp_node("camp-inert-test", x=3, y=7)
        self.engine.nodes.append(camp)
        agent = self.engine.agents[0]
        rule = self.engine.decision_rule
        for need_name in ("hunger", "thirst"):
            candidates = rule._candidates_for_need(self.engine, agent, need_name)
            camp_candidates = [(n, t) for n, t in candidates if n.kind == "camp"]
            self.assertEqual(len(camp_candidates), 0,
                "camps should not appear in candidates for {}".format(need_name))


class ActivityFatigueTests(unittest.TestCase):
    def setUp(self):
        self.config = SimulationConfig(
            days=5, seed=10, num_households=1, members_per_household=2,
            grid_width=12, grid_height=10,
        )
        self.engine = SpatialPrototypeEngine(config=self.config)
        self.agent = self.engine.agents[0]
        self.phys = self.config.physiology
        self.home = self.engine._home_for_agent(self.agent)

    def _place_at_home(self):
        self.agent.x = self.home.x
        self.agent.y = self.home.y
        self.agent.carried_food = 0.0
        self.agent.hunger = 0.0
        self.agent.thirst = 0.0
        self.agent.fatigue = 0.3

    def test_base_fatigue_applied_when_idle(self):
        self.agent.fatigue = 0.0
        self.engine._apply_base_fatigue(self.agent)
        self.assertAlmostEqual(self.agent.fatigue, self.phys.fatigue_increase_per_tick, places=4)

    def test_movement_adds_extra_fatigue_when_not_carrying(self):
        self.agent.fatigue = 0.0
        self.agent.carried_food = 0.0
        self.engine._apply_movement_fatigue(self.agent)
        expected = self.phys.movement_fatigue_per_step
        self.assertAlmostEqual(self.agent.fatigue, 0.0 + expected, places=4)

    def test_no_movement_no_movement_fatigue(self):
        self._place_at_home()
        self.home.stock = self.home.capacity
        with patch.object(self.engine, '_apply_movement_fatigue') as mock:
            self.engine.step()
            mock.assert_not_called()

    def test_carrying_food_scales_movement_fatigue(self):
        self.agent.fatigue = 0.0
        self.agent.carried_food = 0.5 * self.agent.carry_capacity
        self.engine._apply_movement_fatigue(self.agent)
        load_ratio = 0.5
        expected = self.phys.movement_fatigue_per_step + self.phys.carrying_fatigue_per_step_at_full_load * load_ratio
        self.assertAlmostEqual(self.agent.fatigue, 0.0 + expected, places=4)

    def test_full_load_carrying_fatigue_caps_at_full_load(self):
        self.agent.fatigue = 0.0
        self.agent.carried_food = self.agent.carry_capacity * 2.0
        self.engine._apply_movement_fatigue(self.agent)
        load_ratio = 1.0
        expected = self.phys.movement_fatigue_per_step + self.phys.carrying_fatigue_per_step_at_full_load * load_ratio
        self.assertAlmostEqual(self.agent.fatigue, 0.0 + expected, places=4)

    def test_zero_carry_capacity_safe(self):
        self.agent.fatigue = 0.0
        self.agent.carry_capacity = 0.0
        self.agent.carried_food = 0.5
        self.engine._apply_movement_fatigue(self.agent)
        expected = self.phys.movement_fatigue_per_step
        self.assertAlmostEqual(self.agent.fatigue, 0.0 + expected, places=4)

    def test_fatigue_clamped_to_one_with_activity_costs(self):
        self.agent.fatigue = 0.97
        self.agent.carried_food = self.agent.carry_capacity
        self.engine._apply_base_fatigue(self.agent)
        self.engine._apply_movement_fatigue(self.agent)
        self.assertLessEqual(self.agent.fatigue, 1.0)

    def test_decision_rule_unchanged(self):
        import inspect
        from rules.decision import DecisionRule
        source = inspect.getsource(DecisionRule)
        self.assertIn("def choose_plan", source)
        self.assertNotIn("fatigue", source,
            "DecisionRule should not reference fatigue")


if __name__ == "__main__":
    unittest.main()
