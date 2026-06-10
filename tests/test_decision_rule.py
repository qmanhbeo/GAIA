from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

from gaia_config import SimulationConfig
from spatial_simulation import (
    HOME_MEAL_SIZE,
    HUNGER_HOME_THRESHOLD,
    THIRST_WATER_THRESHOLD,
    SpatialPrototypeEngine,
    make_camp_node,
)
from rules.decision import DecisionRule, NeedSpec, SatisfierSpec


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
        with patch.object(self.rule, '_compute_eta', return_value=5):
            best_node, best_task = self.rule._best_viable_target(self.engine, self.agent, candidates)
        self.assertEqual(best_node.id, self.second_food.id,
            "remembered node should win when slack ties")

    def test_better_slack_beats_memory(self):
        candidates = [(self.food, "seek_food"), (self.second_food, "seek_food")]
        self.agent.node_memory[self.food.id] = {}
        with patch.object(self.rule, '_compute_eta',
                          side_effect=lambda e, a, n: {self.food.id: 10, self.second_food.id: 2}.get(n.id, 100)):
            best_node, best_task = self.rule._best_viable_target(self.engine, self.agent, candidates)
        self.assertEqual(best_node.id, self.second_food.id,
            "unknown node with better slack should beat remembered node")

    def test_remembered_depleted_rejected(self):
        self.food.stock = 0.0
        self.agent.node_memory[self.food.id] = {}
        candidates = [(self.food, "seek_food"), (self.second_food, "seek_food")]
        with patch.object(self.rule, '_compute_eta', return_value=5):
            best_node, best_task = self.rule._best_viable_target(self.engine, self.agent, candidates)
        self.assertEqual(best_node.id, self.second_food.id,
            "depleted remembered node should be rejected; stocked unknown should win")

    def test_no_memory_behavior_unchanged(self):
        candidates = [(self.food, "seek_food"), (self.second_food, "seek_food")]
        with patch.object(self.rule, '_compute_eta',
                          side_effect=lambda e, a, n: {self.food.id: 5, self.second_food.id: 3}.get(n.id, 100)):
            best_node, best_task = self.rule._best_viable_target(self.engine, self.agent, candidates)
        self.assertEqual(best_node.id, self.second_food.id,
            "better slack should win when neither candidate is remembered")

    def test_node_memory_only_in_helper(self):
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
        camp = make_camp_node("camp-test", x=3, y=7)
        engine.nodes.append(camp)
        agent = engine.agents[0]
        rule = engine.decision_rule
        for need_name in ("hunger", "thirst"):
            candidates = rule._candidates_for_need(engine, agent, need_name)
            camp_candidates = [(n, t) for n, t in candidates if n.kind == "camp"]
            self.assertEqual(len(camp_candidates), 0,
                "camps should not appear in candidates for {}".format(need_name))


if __name__ == "__main__":
    unittest.main()
