"""Agent decision rule.

Agents commit to a survival task and only override when a critical need
crosses a threshold. When retargeting, the rule evaluates resource stock,
travel ETA, and survival slack to pick the most viable target.
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

    # ------------------------------------------------------------------
    # Path / time helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_eta(engine: Any, agent: Any, node: Any) -> int | None:
        pos = (agent.x, agent.y)
        goal = (node.x, node.y)
        if pos == goal:
            return 0
        path = engine._find_path(pos, goal, {})
        if path is None:
            return None
        return len(path) - 1

    @staticmethod
    def _estimate_death_time(agent: Any, phys: Any) -> int:
        """Approximate ticks until death if no consumption.

        Temporary local estimate pending a shared survival-budget helper.
        Uses the same tick-by-tick projection as the engine's _update_agent.
        """
        h, t, hp = agent.hunger, agent.thirst, agent.health
        h_thresh = phys.hunger_damage_threshold
        t_thresh = phys.thirst_damage_threshold
        ticks = 0
        while hp > 0 and ticks < 100_000:
            h = min(1.0, h + phys.hunger_increase_per_tick)
            t = min(1.0, t + phys.thirst_increase_per_tick)
            if h > h_thresh:
                hp = max(0.0, hp - phys.hunger_damage_rate)
            if t > t_thresh:
                hp = max(0.0, hp - phys.thirst_damage_rate)
            if hp <= 0:
                break
            ticks += 1
        return ticks

    # ------------------------------------------------------------------
    # Task semantics
    # ------------------------------------------------------------------

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
        if agent.task_target_id is not None:
            node = next((n for n in engine.nodes if n.id == agent.task_target_id), None)
            if node is not None:
                return node
        if task == "seek_water":
            return engine._node_by_kind("water")
        if task == "seek_food":
            return engine._node_by_kind("food")
        return engine._home_for_agent(agent)

    # ------------------------------------------------------------------
    # Viability / selection
    # ------------------------------------------------------------------

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
        eta = self._compute_eta(engine, agent, target)
        if eta is None:
            return False
        phys = engine.config.physiology
        death_t = self._estimate_death_time(agent, phys)
        if eta >= death_t:
            return False
        return True

    def _best_viable_target(
        self, engine: Any, agent: Any,
        candidates: list[tuple[Any, str]],
    ) -> tuple[Any, str]:
        """Return (node, task) with highest survival slack.

        Viable means: has stock (for food/water), reachable, and
        survivable (ETA < death_time). Falls back to the first reachable
        candidate with stock, then to the first candidate overall.
        """
        phys = engine.config.physiology
        death_t = self._estimate_death_time(agent, phys)
        best_node, best_task, best_slack = None, None, float("-inf")

        for node, task in candidates:
            if node.kind in ("food", "water") and node.stock <= 0:
                continue
            if task == "seek_home_food" and node.stock < self.home_meal_size:
                continue
            eta = self._compute_eta(engine, agent, node)
            if eta is None:
                continue
            slack = death_t - eta
            if slack > best_slack:
                best_slack = slack
                best_node, best_task = node, task

        # Fallback: first reachable candidate with stock
        if best_node is None:
            for node, task in candidates:
                if node.kind in ("food", "water") and node.stock <= 0:
                    continue
                if task == "seek_home_food" and node.stock < self.home_meal_size:
                    continue
                if self._compute_eta(engine, agent, node) is not None:
                    return node, task
            # Last resort: first candidate (preserves old behaviour)
            if candidates:
                return candidates[0]

        return best_node, best_task

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

    # ------------------------------------------------------------------
    # Main plan
    # ------------------------------------------------------------------

    def choose_plan(self, engine: Any, agent: Any) -> tuple[Any, str]:
        home = engine._home_for_agent(agent)

        # A. Carrying food — return home unless thirst is critical
        if agent.carried_food > 0:
            if agent.current_task == "return_home_with_food" and self._is_task_valid(engine, agent):
                if not self._should_critical_override(engine, agent):
                    return home, "carrying_food_home"
            if agent.thirst >= self.thirst_critical:
                water, _ = self._best_viable_target(
                    engine, agent, [(engine._node_by_kind("water"), "seek_water")]
                )
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
            water, task = self._best_viable_target(
                engine, agent, [(engine._node_by_kind("water"), "seek_water")]
            )
            self._commit(agent, task, water)
            return water, "seeking_water"
        if agent.hunger >= self.hunger_critical:
            candidates = [(n, "seek_food") for n in engine.nodes if n.kind == "food"]
            if home.stock >= self.home_meal_size:
                candidates.append((home, "seek_home_food"))
            target, task = self._best_viable_target(engine, agent, candidates)
            self._commit(agent, task, target)
            return target, self._task_to_state(task)
        # Mild needs — thirst before hunger
        if agent.thirst >= self.thirst_water_threshold:
            water, task = self._best_viable_target(
                engine, agent, [(engine._node_by_kind("water"), "seek_water")]
            )
            self._commit(agent, task, water)
            return water, "seeking_water"
        if agent.hunger >= self.hunger_home_threshold:
            candidates = [(n, "seek_food") for n in engine.nodes if n.kind == "food"]
            if home.stock >= self.home_meal_size:
                candidates.append((home, "seek_home_food"))
            target, task = self._best_viable_target(engine, agent, candidates)
            self._commit(agent, task, target)
            return target, self._task_to_state(task)
        # Maintenance
        if home.stock < home.capacity and agent.carried_food < agent.carry_capacity:
            target, task = self._best_viable_target(
                engine, agent, [(n, "seek_food") for n in engine.nodes if n.kind == "food"]
            )
            self._commit(agent, "seek_food", target)
            return target, "seeking_food"
        # Rest
        self._clear_task(agent)
        return home, "resting"

    def choose_target(self, engine: Any, agent: Any) -> Any:
        return self.choose_plan(engine, agent)[0]
