from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from gaia_config import SPATIAL_MODE, SimulationConfig
from simulation_artifact import SimulationArtifact


@dataclass
class SpatialNode:
    id: str
    kind: str
    label: str
    x: int
    y: int
    stock: float
    capacity: float
    replenish_per_tick: float
    color: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "label": self.label,
            "x": self.x,
            "y": self.y,
            "stock": round(self.stock, 3),
            "capacity": round(self.capacity, 3),
            "stock_ratio": round(self.stock / self.capacity, 3) if self.capacity else 0.0,
            "color": self.color,
        }


@dataclass
class SpatialAgent:
    id: str
    label: str
    x: int
    y: int
    home_x: int
    home_y: int
    hunger: float
    thirst: float
    health: float
    state: str = "idle"
    target_id: str | None = None
    target_kind: str | None = None
    last_action: str = "spawned"

    def is_alive(self) -> bool:
        return self.health > 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "x": self.x,
            "y": self.y,
            "home_x": self.home_x,
            "home_y": self.home_y,
            "hunger": round(self.hunger, 3),
            "thirst": round(self.thirst, 3),
            "health": round(self.health, 3),
            "state": self.state,
            "target_id": self.target_id,
            "target_kind": self.target_kind,
            "last_action": self.last_action,
        }


class SpatialPrototypeEngine:
    def __init__(self, config: SimulationConfig):
        self.config = config
        self.tick = 0
        self.snapshot_frequency = config.snapshot_frequency or 1
        self.nodes = self._build_nodes()
        self.agent_home_map = self._build_home_map()
        self.agents = self._build_agents()
        self.time_series = {
            "tick": [],
            "population": [],
            "avg_health": [],
            "avg_hunger": [],
            "avg_thirst": [],
            "moving_agents": [],
        }
        self.snapshots: list[dict[str, Any]] = []
        self._record_snapshot(force=True)

    def _build_nodes(self) -> list[SpatialNode]:
        width = self.config.grid_width
        height = self.config.grid_height
        home_y_positions = self._home_y_positions()
        nodes = []
        for index, y in enumerate(home_y_positions):
            nodes.append(
                SpatialNode(
                    id=f"home-{index + 1}",
                    kind="home",
                    label=f"Home {index + 1}",
                    x=2,
                    y=y,
                    stock=1.0,
                    capacity=1.0,
                    replenish_per_tick=0.0,
                    color="#ffdd9a",
                )
            )

        nodes.append(
            SpatialNode(
                id="food-1",
                kind="food",
                label="Field",
                x=max(6, width // 2),
                y=max(2, height // 3),
                stock=7.0,
                capacity=7.0,
                replenish_per_tick=0.18,
                color="#9df584",
            )
        )
        nodes.append(
            SpatialNode(
                id="water-1",
                kind="water",
                label="Well",
                x=max(8, width - 4),
                y=min(height - 3, (2 * height) // 3),
                stock=8.0,
                capacity=8.0,
                replenish_per_tick=0.24,
                color="#76d0ff",
            )
        )
        return nodes

    def _home_y_positions(self) -> list[int]:
        if self.config.num_households == 1:
            return [self.config.grid_height // 2]
        spacing = max(2, self.config.grid_height // (self.config.num_households + 1))
        positions = [min(self.config.grid_height - 2, spacing * (index + 1)) for index in range(self.config.num_households)]
        return sorted(set(max(1, pos) for pos in positions))

    def _build_home_map(self) -> dict[int, SpatialNode]:
        homes = [node for node in self.nodes if node.kind == "home"]
        mapping = {}
        for index in range(self.config.num_households):
            mapping[index] = homes[min(index, len(homes) - 1)]
        return mapping

    def _build_agents(self) -> list[SpatialAgent]:
        agents = []
        for household_index in range(self.config.num_households):
            home = self.agent_home_map[household_index]
            for member_index in range(self.config.members_per_household):
                offset_x = member_index % 2
                offset_y = (member_index // 2) - 1
                x = min(self.config.grid_width - 1, home.x + offset_x)
                y = max(0, min(self.config.grid_height - 1, home.y + offset_y))
                agents.append(
                    SpatialAgent(
                        id=f"agent-{household_index + 1}-{member_index + 1}",
                        label=f"A{household_index + 1}.{member_index + 1}",
                        x=x,
                        y=y,
                        home_x=home.x,
                        home_y=home.y,
                        hunger=0.32 + 0.09 * ((member_index + household_index) % 4),
                        thirst=0.34 + 0.11 * ((member_index * 2 + household_index) % 3),
                        health=1.0,
                    )
                )
        return agents

    def _node_by_kind(self, kind: str, preferred_home: tuple[int, int] | None = None) -> SpatialNode:
        candidates = [node for node in self.nodes if node.kind == kind]
        if kind != "home" or preferred_home is None:
            return candidates[0]
        home_x, home_y = preferred_home
        return min(candidates, key=lambda node: abs(node.x - home_x) + abs(node.y - home_y))

    def _choose_target(self, agent: SpatialAgent) -> SpatialNode:
        if agent.thirst >= 0.58:
            return self._node_by_kind("water")
        if agent.hunger >= 0.5:
            return self._node_by_kind("food")
        return self._node_by_kind("home", preferred_home=(agent.home_x, agent.home_y))

    @staticmethod
    def _step_axis(delta: int) -> int:
        if delta == 0:
            return 0
        return 1 if delta > 0 else -1

    def _move_agent_toward(self, agent: SpatialAgent, node: SpatialNode) -> None:
        dx = node.x - agent.x
        dy = node.y - agent.y
        if abs(dx) >= abs(dy) and dx != 0:
            agent.x += self._step_axis(dx)
        elif dy != 0:
            agent.y += self._step_axis(dy)
        else:
            return
        agent.state = "moving"
        agent.last_action = f"move:{node.kind}"

    def _consume_from_node(self, agent: SpatialAgent, node: SpatialNode) -> None:
        if node.kind == "food":
            if node.stock >= 0.22:
                node.stock = max(0.0, node.stock - 0.22)
                agent.hunger = max(0.0, agent.hunger - 0.62)
                agent.state = "eating"
                agent.last_action = "eat"
            else:
                agent.state = "waiting"
                agent.last_action = "wait:food"
        elif node.kind == "water":
            if node.stock >= 0.22:
                node.stock = max(0.0, node.stock - 0.22)
                agent.thirst = max(0.0, agent.thirst - 0.74)
                agent.state = "drinking"
                agent.last_action = "drink"
            else:
                agent.state = "waiting"
                agent.last_action = "wait:water"
        else:
            agent.health = min(1.0, agent.health + 0.012)
            agent.state = "resting"
            agent.last_action = "rest"

    def _update_agent(self, agent: SpatialAgent) -> None:
        if not agent.is_alive():
            agent.state = "dead"
            agent.target_id = None
            agent.target_kind = None
            agent.last_action = "dead"
            return

        agent.hunger = min(1.0, agent.hunger + 0.032)
        agent.thirst = min(1.0, agent.thirst + 0.041)
        if agent.hunger > 0.88:
            agent.health = max(0.0, agent.health - 0.016)
        if agent.thirst > 0.91:
            agent.health = max(0.0, agent.health - 0.022)

        target = self._choose_target(agent)
        agent.target_id = target.id
        agent.target_kind = target.kind

        if (agent.x, agent.y) == (target.x, target.y):
            self._consume_from_node(agent, target)
        else:
            self._move_agent_toward(agent, target)

    def _record_metrics(self) -> None:
        alive_agents = [agent for agent in self.agents if agent.is_alive()]
        count = len(alive_agents)
        self.time_series["tick"].append(self.tick)
        self.time_series["population"].append(count)
        self.time_series["avg_health"].append(round(sum(agent.health for agent in alive_agents) / count, 4) if count else 0.0)
        self.time_series["avg_hunger"].append(round(sum(agent.hunger for agent in alive_agents) / count, 4) if count else 0.0)
        self.time_series["avg_thirst"].append(round(sum(agent.thirst for agent in alive_agents) / count, 4) if count else 0.0)
        self.time_series["moving_agents"].append(sum(1 for agent in alive_agents if agent.state == "moving"))

    def _record_snapshot(self, force: bool = False) -> None:
        if not force and self.tick % self.snapshot_frequency != 0:
            return
        self.snapshots.append(self.snapshot())

    def step(self) -> dict[str, Any]:
        self.tick += 1
        for node in self.nodes:
            node.stock = min(node.capacity, node.stock + node.replenish_per_tick)
        for agent in self.agents:
            self._update_agent(agent)
        self._record_metrics()
        self._record_snapshot()
        return self.snapshot()

    def run(self) -> dict[str, list[Any]]:
        while self.tick < self.config.days:
            self.step()
        return self.time_series

    def snapshot(self) -> dict[str, Any]:
        alive_agents = [agent for agent in self.agents if agent.is_alive()]
        selected_agent = max(self.agents, key=lambda agent: (agent.hunger + agent.thirst, agent.health), default=None)
        selected = selected_agent.as_dict() if selected_agent else None
        return {
            "tick": self.tick,
            "grid": {
                "width": self.config.grid_width,
                "height": self.config.grid_height,
                "tile_size": 1,
            },
            "nodes": [node.as_dict() for node in self.nodes],
            "agents": [agent.as_dict() for agent in self.agents],
            "metrics": {
                "population": len(alive_agents),
                "avg_health": round(sum(agent.health for agent in alive_agents) / len(alive_agents), 4) if alive_agents else 0.0,
                "avg_hunger": round(sum(agent.hunger for agent in alive_agents) / len(alive_agents), 4) if alive_agents else 0.0,
                "avg_thirst": round(sum(agent.thirst for agent in alive_agents) / len(alive_agents), 4) if alive_agents else 0.0,
            },
            "selected_agent": selected,
        }

    def build_artifact(self) -> SimulationArtifact:
        if not self.time_series["tick"] and self.tick == 0:
            self._record_metrics()
        return SimulationArtifact(
            metadata={
                "engine_version": "spatial-v1-prototype",
                "mode": SPATIAL_MODE,
                "seed": self.config.seed,
                "config": self.config.to_dict(),
                "viewer_kind": "pixi_spatial_replay_v1",
                "tick_duration_ms": 280,
            },
            time_series=self.time_series,
            final_state=self.snapshot(),
            snapshots=list(self.snapshots),
        )

    def run_artifact(self) -> SimulationArtifact:
        if self.tick < self.config.days:
            self.run()
        return self.build_artifact()
