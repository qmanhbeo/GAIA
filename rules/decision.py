"""Agent decision rule.

The current rule is intentionally simple and threshold-based. Agents
re-evaluate their target every tick, which can cause oscillation between
food, water, and home under competing deficits.

The next decision model should use homeostatic/allostatic task commitment:
agents commit to a survival task long enough to complete it unless another
need crosses a critical override threshold.

See docs/theory/motivation_model.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class DecisionRule:
    hunger_home_threshold: float = 0.5
    home_meal_size: float = 0.25
    thirst_water_threshold: float = 0.86
    hunger_critical: float = 0.88
    thirst_critical: float = 0.91

    @staticmethod
    def _task_to_state(task: str) -> str:
        mapping = {
            "seek_water": "seeking_water",
            "seek_food": "seeking_food",
            "return_home_with_food": "carrying_food_home",
            "seek_home_food": "seeking_home_food",
        }
        return mapping.get(task, "resting")

    @staticmethod
    def _task_target(engine: Any, agent: Any, task: str) -> Any:
        if task == "seek_water":
            return engine._node_by_kind("water")
        if task == "seek_food":
            return engine._node_by_kind("food")
        return engine._home_for_agent(agent)

    def _is_task_valid(self, engine: Any, agent: Any) -> bool:
        if agent.current_task is None or agent.task_target_id is None:
            return False
        target = next((n for n in engine.nodes if n.id == agent.task_target_id), None)
        if target is None:
            return False
        if target.kind in ("food", "water") and target.stock <= 0:
            return False
        if agent.current_task == "seek_home_food":
            home = engine._home_for_agent(agent)
            if home.stock < self.home_meal_size:
                return False
        if agent.current_task == "return_home_with_food":
            if agent.carried_food <= 0:
                return False
        return True

    def _should_critical_override(self, engine: Any, agent: Any) -> bool:
        task = agent.current_task
        if task == "seek_water":
            return agent.hunger >= self.hunger_critical
        if task in ("seek_food", "seek_home_food"):
            return agent.thirst >= self.thirst_critical
        if task == "return_home_with_food":
            return agent.thirst >= self.thirst_critical
        return False

    @staticmethod
    def _commit(agent: Any, task: str, target: Any) -> None:
        agent.current_task = task
        agent.task_target_id = target.id
        agent.task_started_tick = None

    @staticmethod
    def _clear_task(agent: Any) -> None:
        agent.current_task = None
        agent.task_target_id = None
        agent.task_started_tick = None

    def choose_plan(self, engine: Any, agent: Any) -> tuple[Any, str]:
        home = engine._home_for_agent(agent)

        # A. Carrying food — return home unless thirst is critical
        if agent.carried_food > 0:
            if agent.current_task == "return_home_with_food" and self._is_task_valid(engine, agent):
                if not self._should_critical_override(engine, agent):
                    return home, "carrying_food_home"
            if agent.thirst >= self.thirst_critical:
                water = engine._node_by_kind("water")
                self._commit(agent, "seek_water", water)
                return water, "seeking_water"
            self._commit(agent, "return_home_with_food", home)
            return home, "carrying_food_home"

        # B. Continue valid current task
        if agent.current_task is not None:
            if self._is_task_valid(engine, agent) and not self._should_critical_override(engine, agent):
                target = self._task_target(engine, agent, agent.current_task)
                return target, self._task_to_state(agent.current_task)
            self._clear_task(agent)

        # C. Fresh task selection — critical needs first
        if agent.thirst >= self.thirst_critical:
            water = engine._node_by_kind("water")
            self._commit(agent, "seek_water", water)
            return water, "seeking_water"
        if agent.hunger >= self.hunger_critical:
            if home.stock >= self.home_meal_size:
                self._commit(agent, "seek_home_food", home)
                return home, "seeking_home_food"
            food = engine._node_by_kind("food")
            self._commit(agent, "seek_food", food)
            return food, "seeking_food"
        # Mild needs — thirst before hunger
        if agent.thirst >= self.thirst_water_threshold:
            water = engine._node_by_kind("water")
            self._commit(agent, "seek_water", water)
            return water, "seeking_water"
        if agent.hunger >= self.hunger_home_threshold:
            if home.stock >= self.home_meal_size:
                self._commit(agent, "seek_home_food", home)
                return home, "seeking_home_food"
            food = engine._node_by_kind("food")
            self._commit(agent, "seek_food", food)
            return food, "seeking_food"
        # Maintenance
        if home.stock < home.capacity and agent.carried_food < agent.carry_capacity:
            food = engine._node_by_kind("food")
            self._commit(agent, "seek_food", food)
            return food, "seeking_food"
        # Rest
        self._clear_task(agent)
        return home, "resting"

    def choose_target(self, engine: Any, agent: Any) -> Any:
        return self.choose_plan(engine, agent)[0]
