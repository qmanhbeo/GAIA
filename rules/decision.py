from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class DecisionRule:
    hunger_home_threshold: float = 0.5
    home_meal_size: float = 0.25
    thirst_water_threshold: float = 0.86

    def choose_plan(self, engine: Any, agent: Any) -> tuple[Any, str]:
        home = engine._home_for_agent(agent)
        if agent.carried_food > 0:
            return home, "carrying_food_home"
        if agent.hunger >= self.hunger_home_threshold:
            if home.stock >= self.home_meal_size:
                return home, "seeking_home_food"
            return engine._node_by_kind("food"), "seeking_food"
        if agent.thirst >= self.thirst_water_threshold:
            return engine._node_by_kind("water"), "seeking_water"
        if home.stock < home.capacity and agent.carried_food < agent.carry_capacity:
            return engine._node_by_kind("food"), "seeking_food"
        return home, "resting"

    def choose_target(self, engine: Any, agent: Any) -> Any:
        return self.choose_plan(engine, agent)[0]
