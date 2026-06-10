from __future__ import annotations

import unittest

from gaia_config import SimulationConfig
from spatial_simulation import SpatialPrototypeEngine, make_camp_node


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


if __name__ == "__main__":
    unittest.main()
