from __future__ import annotations

import unittest

from gaia_config import PhysiologyConfig, SimulationConfig
from spatial_simulation import SpatialPrototypeEngine
from rules.decision import DecisionRule
from rules.resources import ResourceRule


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


if __name__ == "__main__":
    unittest.main()
