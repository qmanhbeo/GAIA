"""Agent decision rule.

Agents commit to a survival task and only override when a critical need
crosses a threshold. When retargeting, the rule evaluates resource stock,
travel ETA, and survival slack to pick the most viable target.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class NeedSpec:
    name: str
    agent_attr: str
    critical_threshold: float
    mild_threshold: float | None = None


@dataclass
class SatisfierSpec:
    need_name: str
    task_name: str
    target_kind: str
    is_home_satisfier: bool = False
    requires_stock: bool = True
    min_stock: float | None = None


@dataclass
class DecisionRule:
    hunger_home_threshold: float = 0.5
    home_meal_size: float = 0.25
    thirst_water_threshold: float = 0.86
    hunger_critical: float = 0.88
    thirst_critical: float = 0.91

    MEMORY_TIE_EPSILON = 1e-9

    def __post_init__(self) -> None:
        self.NEEDS: list[NeedSpec] = [
            NeedSpec(
                name="hunger", agent_attr="hunger",
                critical_threshold=self.hunger_critical,
                mild_threshold=self.hunger_home_threshold,
            ),
            NeedSpec(
                name="thirst", agent_attr="thirst",
                critical_threshold=self.thirst_critical,
                mild_threshold=self.thirst_water_threshold,
            ),
        ]
        self.SATISFIERS: dict[str, list[SatisfierSpec]] = {
            "hunger": [
                SatisfierSpec(
                    need_name="hunger", task_name="seek_food",
                    target_kind="food", requires_stock=True,
                ),
                SatisfierSpec(
                    need_name="hunger", task_name="seek_home_food",
                    target_kind="home", is_home_satisfier=True,
                    requires_stock=True, min_stock=self.home_meal_size,
                ),
            ],
            "thirst": [
                SatisfierSpec(
                    need_name="thirst", task_name="seek_water",
                    target_kind="water", requires_stock=True,
                ),
            ],
        }

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
    # Spec-driven helpers
    # ------------------------------------------------------------------

    def _candidates_for_need(self, engine: Any, agent: Any, need_name: str) -> list[tuple[Any, str]]:
        candidates: list[tuple[Any, str]] = []
        home = engine._home_for_agent(agent)
        for sat in self.SATISFIERS.get(need_name, []):
            if sat.is_home_satisfier:
                if sat.min_stock is not None and home.stock < sat.min_stock:
                    continue
                candidates.append((home, sat.task_name))
            else:
                for node in engine.nodes:
                    if node.kind == sat.target_kind:
                        candidates.append((node, sat.task_name))
        return candidates

    def _satisfier_for_task(self, task: str) -> SatisfierSpec | None:
        for satisfiers in self.SATISFIERS.values():
            for sat in satisfiers:
                if sat.task_name == task:
                    return sat
        return None

    def _candidate_is_depleted(self, node: Any, task: str) -> bool:
        sat = self._satisfier_for_task(task)
        if sat is None or not sat.requires_stock:
            return False
        if sat.min_stock is not None:
            return node.stock < sat.min_stock
        return node.stock <= 0

    @staticmethod
    def _candidate_memory_score(agent: Any, node: Any) -> int:
        return 1 if node.id in agent.node_memory else 0

    # ------------------------------------------------------------------
    # Viability / selection
    # ------------------------------------------------------------------

    def _is_task_valid(self, engine: Any, agent: Any) -> bool:
        if agent.current_task is None or agent.task_target_id is None:
            return False
        target = next((n for n in engine.nodes if n.id == agent.task_target_id), None)
        if target is None:
            return False
        if self._candidate_is_depleted(target, agent.current_task):
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
            if self._candidate_is_depleted(node, task):
                continue
            eta = self._compute_eta(engine, agent, node)
            if eta is None:
                continue
            slack = death_t - eta
            if slack > best_slack + self.MEMORY_TIE_EPSILON:
                best_slack = slack
                best_node, best_task = node, task
            elif abs(slack - best_slack) <= self.MEMORY_TIE_EPSILON:
                current_mem = self._candidate_memory_score(agent, best_node) if best_node is not None else 0
                candidate_mem = self._candidate_memory_score(agent, node)
                if candidate_mem > current_mem:
                    best_slack = slack
                    best_node, best_task = node, task

        # Fallback: first reachable candidate with stock
        if best_node is None:
            for node, task in candidates:
                if self._candidate_is_depleted(node, task):
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
            candidates = self._candidates_for_need(engine, agent, "thirst")
            water, task = self._best_viable_target(engine, agent, candidates)
            self._commit(agent, task, water)
            return water, "seeking_water"
        if agent.hunger >= self.hunger_critical:
            candidates = self._candidates_for_need(engine, agent, "hunger")
            target, task = self._best_viable_target(engine, agent, candidates)
            self._commit(agent, task, target)
            return target, self._task_to_state(task)
        # Mild needs — thirst before hunger
        if agent.thirst >= self.thirst_water_threshold:
            candidates = self._candidates_for_need(engine, agent, "thirst")
            water, task = self._best_viable_target(engine, agent, candidates)
            self._commit(agent, task, water)
            return water, "seeking_water"
        if agent.hunger >= self.hunger_home_threshold:
            candidates = self._candidates_for_need(engine, agent, "hunger")
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
