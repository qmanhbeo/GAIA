from __future__ import annotations

import inspect
import unittest
from unittest.mock import patch

from gaia_config import PhysiologyConfig, SimulationConfig
from spatial_simulation import (
    HOME_MEAL_SIZE,
    HUNGER_HOME_THRESHOLD,
    SpatialPrototypeEngine,
    make_camp_node,
)
from rules.decision import DecisionRule


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
        camp = make_camp_node("camp-default", x=3, y=7)
        self.assertEqual(camp.rest_safety, 0.0)

    def test_custom_camp_rest_safety_matches_shelter_quality(self):
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

    def test_camps_remain_inert(self):
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


class FatigueDecisionTests(unittest.TestCase):
    def setUp(self):
        self.config = SimulationConfig(
            days=5, seed=10, num_households=1, members_per_household=2,
            grid_width=12, grid_height=10,
        )
        self.engine = SpatialPrototypeEngine(config=self.config)
        self.agent = self.engine.agents[0]
        self.phys = self.config.physiology
        self.home = self.engine._home_for_agent(self.agent)

    def test_high_fatigue_low_needs_seeks_rest(self):
        self.agent.fatigue = 0.8
        self.agent.hunger = 0.0
        self.agent.thirst = 0.0
        target, state = self.engine.decision_rule.choose_plan(self.engine, self.agent)
        self.assertEqual(target.id, self.home.id)
        self.assertEqual(state, "seeking_rest")

    def test_critical_thirst_overrides_high_fatigue(self):
        self.agent.fatigue = 0.8
        self.agent.thirst = 0.95
        self.agent.hunger = 0.0
        target, state = self.engine.decision_rule.choose_plan(self.engine, self.agent)
        self.assertEqual(target.kind, "water")
        self.assertEqual(state, "seeking_water")

    def test_critical_hunger_overrides_high_fatigue(self):
        self.agent.fatigue = 0.8
        self.agent.hunger = 0.9
        self.agent.thirst = 0.0
        target, state = self.engine.decision_rule.choose_plan(self.engine, self.agent)
        self.assertIn(state, ("seeking_food", "seeking_home_food"),
            "critical hunger should route to food or home food target")

    def test_mild_thirst_overrides_high_fatigue(self):
        self.agent.fatigue = 0.8
        self.agent.thirst = 0.87
        self.agent.hunger = 0.0
        target, state = self.engine.decision_rule.choose_plan(self.engine, self.agent)
        self.assertEqual(target.kind, "water")
        self.assertEqual(state, "seeking_water")

    def test_mild_hunger_overrides_high_fatigue(self):
        self.agent.fatigue = 0.8
        self.agent.hunger = 0.6
        self.agent.thirst = 0.0
        self.home.stock = 1.0
        target, state = self.engine.decision_rule.choose_plan(self.engine, self.agent)
        self.assertEqual(state, "seeking_home_food")

    def test_below_threshold_fatigue_does_not_seek_rest(self):
        self.agent.fatigue = 0.5
        self.agent.hunger = 0.0
        self.agent.thirst = 0.0
        target, state = self.engine.decision_rule.choose_plan(self.engine, self.agent)
        self.assertNotEqual(state, "seeking_rest",
            "agent with fatigue below threshold should not seek rest")

    def test_high_fatigue_never_chooses_camp(self):
        camp = make_camp_node("camp-fatigue-test", x=3, y=7)
        self.engine.nodes.append(camp)
        self.agent.fatigue = 0.8
        self.agent.hunger = 0.0
        self.agent.thirst = 0.0
        target, state = self.engine.decision_rule.choose_plan(self.engine, self.agent)
        self.assertEqual(target.kind, "home",
            "high fatigue should target home, not camp")

    def test_seek_rest_task_cleared_after_home_rest(self):
        self.agent.x = self.home.x
        self.agent.y = self.home.y
        self.agent.current_task = "seek_rest"
        self.agent.task_target_id = self.home.id
        self.agent.carried_food = 0.0
        self.agent.hunger = 0.0
        self.agent.thirst = 0.0
        self.home.stock = self.home.capacity
        self.engine._handle_home_arrival(self.agent, self.home)
        self.assertIsNone(self.agent.current_task,
            "seek_rest task should be cleared after home rest")
        self.assertIsNone(self.agent.task_target_id,
            "task target id should be cleared after home rest")

    def test_decision_rule_references_fatigue_intentionally(self):
        from rules.decision import DecisionRule
        source = inspect.getsource(DecisionRule)
        self.assertIn("fatigue", source,
            "DecisionRule should now reference fatigue")
        self.assertNotIn('"fatigue"', source,
            "fatigue should not be a NeedSpec string key")


class FatigueObservabilityTests(unittest.TestCase):
    def setUp(self):
        self.config = SimulationConfig(
            days=5, seed=10, num_households=1, members_per_household=2,
            grid_width=12, grid_height=10,
        )
        self.engine = SpatialPrototypeEngine(config=self.config)

    def test_time_series_has_fatigue_metrics_after_step(self):
        self.engine.step()
        keys = {"avg_fatigue", "max_fatigue", "resting_count", "seeking_rest_count", "fatigued_count"}
        self.assertTrue(keys.issubset(self.engine.time_series),
            f"Missing keys: {keys - set(self.engine.time_series)}")
        self.assertEqual(len(self.engine.time_series["avg_fatigue"]), 1)

    def test_avg_fatigue_is_within_bounds(self):
        for _ in range(5):
            self.engine.step()
        vals = self.engine.time_series["avg_fatigue"]
        for v in vals:
            self.assertIsInstance(v, float)
            self.assertGreaterEqual(v, 0.0)
            self.assertLessEqual(v, 1.0)

    def test_max_fatigue_is_within_bounds(self):
        for _ in range(5):
            self.engine.step()
        vals = self.engine.time_series["max_fatigue"]
        for v in vals:
            self.assertIsInstance(v, float)
            self.assertGreaterEqual(v, 0.0)
            self.assertLessEqual(v, 1.0)

    def test_resting_count_nonnegative(self):
        for _ in range(5):
            self.engine.step()
        vals = self.engine.time_series["resting_count"]
        for v in vals:
            self.assertIsInstance(v, int)
            self.assertGreaterEqual(v, 0)

    def test_seeking_rest_count_nonnegative(self):
        for _ in range(5):
            self.engine.step()
        vals = self.engine.time_series["seeking_rest_count"]
        for v in vals:
            self.assertIsInstance(v, int)
            self.assertGreaterEqual(v, 0)

    def test_fatigued_count_matches_threshold(self):
        phys = PhysiologyConfig(
            hunger_increase_per_tick=0.001,
            thirst_increase_per_tick=0.001,
        )
        config = SimulationConfig(
            days=40, seed=42, num_households=1, members_per_household=2,
            grid_width=12, grid_height=10, physiology=phys,
        )
        engine = SpatialPrototypeEngine(config=config)
        threshold = config.physiology.fatigue_rest_threshold
        for _ in range(40):
            engine.step()
            count = engine.time_series["fatigued_count"][-1]
            actual = sum(1 for a in engine.agents if a.is_alive() and a.fatigue >= threshold)
            self.assertEqual(count, actual,
                f"tick {engine.tick}: fatigued_count {count} != actual {actual}")

    def test_snapshot_metrics_include_fatigue_fields(self):
        snapshot = self.engine.snapshot()
        m = snapshot["metrics"]
        for key in ("avg_fatigue", "max_fatigue", "resting_count", "seeking_rest_count", "fatigued_count"):
            self.assertIn(key, m, f"metrics missing key: {key}")
        self.assertIn("avg_fatigue", snapshot)
        self.assertIn("max_fatigue", snapshot)


if __name__ == "__main__":
    unittest.main()
