from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush
from typing import Any

from gaia_config import SPATIAL_MODE, SimulationConfig
from simulation_artifact import SimulationArtifact


SPATIAL_ENGINE_VERSION = "spatial-v1b-topology"


@dataclass
class SpatialTile:
    x: int
    y: int
    kind: str
    movement_cost: int
    passable: bool
    occupancy_limit: int
    color: str

    def as_dict(self, occupied: int = 0) -> dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
            "kind": self.kind,
            "movement_cost": self.movement_cost,
            "passable": self.passable,
            "occupancy_limit": self.occupancy_limit,
            "occupied": occupied,
            "color": self.color,
        }


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
    move_cooldown: int = 0
    path_length: int | None = None

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
            "move_cooldown": self.move_cooldown,
            "path_length": self.path_length,
        }


class SpatialPrototypeEngine:
    def __init__(self, config: SimulationConfig):
        self.config = config
        self.tick = 0
        self.snapshot_frequency = config.snapshot_frequency or 1
        self.nodes = self._build_nodes()
        self.tiles = self._build_tiles()
        self.agent_home_map = self._build_home_map()
        self.agents = self._build_agents()
        self.time_series = {
            "tick": [],
            "population": [],
            "avg_health": [],
            "avg_hunger": [],
            "avg_thirst": [],
            "moving_agents": [],
            "blocked_agents": [],
            "food_stock": [],
            "water_stock": [],
        }
        self.snapshots: list[dict[str, Any]] = []
        self._record_snapshot(force=True)

    def _barrier_x(self) -> int | None:
        if self.config.grid_width < 10:
            return None
        return max(4, self.config.grid_width // 2 - 2)

    def _gap_y(self) -> int | None:
        if self._barrier_x() is None or self.config.grid_height < 6:
            return None
        return max(1, min(self.config.grid_height - 2, self.config.grid_height // 2 - 1))

    def _home_y_positions(self) -> list[int]:
        if self.config.num_households == 1:
            return [self.config.grid_height // 2]
        spacing = max(2, self.config.grid_height // (self.config.num_households + 1))
        positions = [min(self.config.grid_height - 2, spacing * (index + 1)) for index in range(self.config.num_households)]
        return sorted(set(max(1, pos) for pos in positions))

    def _build_nodes(self) -> list[SpatialNode]:
        width = self.config.grid_width
        height = self.config.grid_height
        barrier_x = self._barrier_x()
        home_y_positions = self._home_y_positions()
        home_x = min(2, width - 1)
        food_y = max(2, height // 3)
        water_y = min(height - 3, (2 * height) // 3)

        if barrier_x is None:
            food_x = min(width - 3, max(home_x + 3, width // 2))
        else:
            food_x = min(width - 3, max(home_x + 3, barrier_x + 2))
        water_x = min(width - 2, max(food_x + 2, width - 4))
        if water_x <= food_x:
            water_x = min(width - 1, food_x + 1)

        nodes = []
        for index, y in enumerate(home_y_positions):
            nodes.append(
                SpatialNode(
                    id=f"home-{index + 1}",
                    kind="home",
                    label=f"Home {index + 1}",
                    x=home_x,
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
                x=food_x,
                y=food_y,
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
                x=water_x,
                y=water_y,
                stock=8.0,
                capacity=8.0,
                replenish_per_tick=0.24,
                color="#76d0ff",
            )
        )
        return nodes

    def _build_tiles(self) -> dict[tuple[int, int], SpatialTile]:
        tiles: dict[tuple[int, int], SpatialTile] = {}
        width = self.config.grid_width
        height = self.config.grid_height
        for y in range(height):
            for x in range(width):
                tiles[(x, y)] = SpatialTile(
                    x=x,
                    y=y,
                    kind="plain",
                    movement_cost=1,
                    passable=True,
                    occupancy_limit=1,
                    color="#0d1a28",
                )

        gap_y = self._gap_y()
        barrier_x = self._barrier_x()
        if gap_y is not None:
            for x in range(width):
                self._set_tile(tiles, x, gap_y, kind="road", movement_cost=1, passable=True, occupancy_limit=1, color="#152a3b")
        if barrier_x is not None:
            for y in range(1, height - 1):
                if y == gap_y:
                    continue
                self._set_tile(tiles, barrier_x, y, kind="rock", movement_cost=0, passable=False, occupancy_limit=0, color="#233547")

        food = self._node_by_kind_from(self.nodes, "food")
        water = self._node_by_kind_from(self.nodes, "water")
        for x in range(max(0, food.x - 1), min(width, food.x + 2)):
            for y in range(max(0, food.y - 1), min(height, food.y + 2)):
                if (x, y) == (food.x, food.y) or y == gap_y:
                    continue
                self._set_tile(tiles, x, y, kind="brush", movement_cost=2, passable=True, occupancy_limit=1, color="#173624")

        for x in range(max(0, water.x - 1), min(width, water.x + 2)):
            for y in range(max(0, water.y - 1), min(height, water.y + 2)):
                if (x, y) == (water.x, water.y) or y == gap_y:
                    continue
                self._set_tile(tiles, x, y, kind="marsh", movement_cost=3, passable=True, occupancy_limit=1, color="#153244")

        for home in [node for node in self.nodes if node.kind == "home"]:
            self._set_tile(
                tiles,
                home.x,
                home.y,
                kind="plain",
                movement_cost=1,
                passable=True,
                occupancy_limit=max(2, self.config.members_per_household),
                color="#16202e",
            )

        for node in [node for node in self.nodes if node.kind in {"food", "water"}]:
            base_tile = tiles[(node.x, node.y)]
            self._set_tile(
                tiles,
                node.x,
                node.y,
                kind=base_tile.kind,
                movement_cost=1,
                passable=True,
                occupancy_limit=1,
                color=base_tile.color,
            )

        return tiles

    def _build_home_map(self) -> dict[int, SpatialNode]:
        homes = [node for node in self.nodes if node.kind == "home"]
        mapping = {}
        for index in range(self.config.num_households):
            mapping[index] = homes[min(index, len(homes) - 1)]
        return mapping

    def _build_agents(self) -> list[SpatialAgent]:
        agents = []
        occupied: dict[tuple[int, int], int] = {}
        for household_index in range(self.config.num_households):
            home = self.agent_home_map[household_index]
            candidates = self._spawn_candidates(home)
            for member_index in range(self.config.members_per_household):
                x, y = self._choose_spawn_position(candidates, occupied)
                occupied[(x, y)] = occupied.get((x, y), 0) + 1
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

    @staticmethod
    def _node_by_kind_from(nodes: list[SpatialNode], kind: str, preferred_home: tuple[int, int] | None = None) -> SpatialNode:
        candidates = [node for node in nodes if node.kind == kind]
        if kind != "home" or preferred_home is None:
            return candidates[0]
        home_x, home_y = preferred_home
        return min(candidates, key=lambda node: abs(node.x - home_x) + abs(node.y - home_y))

    def _set_tile(
        self,
        tiles: dict[tuple[int, int], SpatialTile],
        x: int,
        y: int,
        *,
        kind: str,
        movement_cost: int,
        passable: bool,
        occupancy_limit: int,
        color: str,
    ) -> None:
        tile = tiles[(x, y)]
        tile.kind = kind
        tile.movement_cost = movement_cost
        tile.passable = passable
        tile.occupancy_limit = occupancy_limit
        tile.color = color

    def _spawn_candidates(self, home: SpatialNode) -> list[tuple[int, int]]:
        candidates: list[tuple[int, int]] = []
        for radius in range(0, 5):
            for y in range(max(0, home.y - radius), min(self.config.grid_height, home.y + radius + 1)):
                for x in range(max(0, home.x), min(self.config.grid_width, home.x + radius + 2)):
                    if (x, y) in candidates:
                        continue
                    tile = self.tiles[(x, y)]
                    if tile.passable:
                        candidates.append((x, y))
        if (home.x, home.y) not in candidates:
            candidates.insert(0, (home.x, home.y))
        candidates.sort(key=lambda position: (abs(position[0] - home.x) + abs(position[1] - home.y), position[1], position[0]))
        return candidates

    def _choose_spawn_position(self, candidates: list[tuple[int, int]], occupied: dict[tuple[int, int], int]) -> tuple[int, int]:
        for position in candidates:
            tile = self.tiles[position]
            if occupied.get(position, 0) < tile.occupancy_limit:
                return position
        return candidates[0]

    def _node_by_kind(self, kind: str, preferred_home: tuple[int, int] | None = None) -> SpatialNode:
        return self._node_by_kind_from(self.nodes, kind, preferred_home=preferred_home)

    def _choose_target(self, agent: SpatialAgent) -> SpatialNode:
        if agent.thirst >= 0.58:
            return self._node_by_kind("water")
        if agent.hunger >= 0.5:
            return self._node_by_kind("food")
        return self._node_by_kind("home", preferred_home=(agent.home_x, agent.home_y))

    def _tile(self, position: tuple[int, int]) -> SpatialTile:
        return self.tiles[position]

    def _occupancy_counts(self) -> dict[tuple[int, int], int]:
        counts: dict[tuple[int, int], int] = {}
        for agent in self.agents:
            if not agent.is_alive():
                continue
            position = (agent.x, agent.y)
            counts[position] = counts.get(position, 0) + 1
        return counts

    @staticmethod
    def _release_occupancy(occupied: dict[tuple[int, int], int], position: tuple[int, int]) -> None:
        if position not in occupied:
            return
        occupied[position] -= 1
        if occupied[position] <= 0:
            occupied.pop(position, None)

    @staticmethod
    def _reserve_occupancy(occupied: dict[tuple[int, int], int], position: tuple[int, int]) -> None:
        occupied[position] = occupied.get(position, 0) + 1

    def _neighbors(self, position: tuple[int, int]) -> list[tuple[int, int]]:
        x, y = position
        candidates = []
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            next_x = x + dx
            next_y = y + dy
            if 0 <= next_x < self.config.grid_width and 0 <= next_y < self.config.grid_height:
                candidates.append((next_x, next_y))
        return candidates

    def _find_path(
        self,
        start: tuple[int, int],
        goal: tuple[int, int],
        occupied: dict[tuple[int, int], int],
    ) -> list[tuple[int, int]] | None:
        if start == goal:
            return [start]

        frontier: list[tuple[int, int, tuple[int, int]]] = []
        heappush(frontier, (0, 0, start))
        came_from: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
        cost_so_far: dict[tuple[int, int], int] = {start: 0}

        while frontier:
            _, steps, current = heappop(frontier)
            if current == goal:
                break
            for neighbor in self._neighbors(current):
                tile = self._tile(neighbor)
                if not tile.passable:
                    continue
                if neighbor != goal and occupied.get(neighbor, 0) >= tile.occupancy_limit:
                    continue
                next_cost = cost_so_far[current] + tile.movement_cost
                if next_cost < cost_so_far.get(neighbor, 1_000_000):
                    cost_so_far[neighbor] = next_cost
                    heuristic = abs(goal[0] - neighbor[0]) + abs(goal[1] - neighbor[1])
                    heappush(frontier, (next_cost + heuristic, steps + 1, neighbor))
                    came_from[neighbor] = current

        if goal not in came_from:
            return None

        path = [goal]
        current = goal
        while current != start:
            current = came_from[current]
            if current is None:
                break
            path.append(current)
        path.reverse()
        return path

    def _move_agent_toward(self, agent: SpatialAgent, node: SpatialNode, occupied: dict[tuple[int, int], int]) -> None:
        current = (agent.x, agent.y)
        goal = (node.x, node.y)
        self._release_occupancy(occupied, current)
        path = self._find_path(current, goal, occupied)
        if not path or len(path) < 2:
            self._reserve_occupancy(occupied, current)
            agent.state = "blocked"
            agent.last_action = f"blocked:{node.kind}"
            agent.path_length = None
            return

        next_position = path[1]
        next_tile = self._tile(next_position)
        if occupied.get(next_position, 0) >= next_tile.occupancy_limit:
            self._reserve_occupancy(occupied, current)
            agent.state = "waiting"
            agent.last_action = f"wait:occupied:{node.kind}"
            agent.path_length = len(path) - 1
            return

        agent.x, agent.y = next_position
        agent.move_cooldown = max(0, next_tile.movement_cost - 1)
        agent.path_length = len(path) - 1
        agent.state = "moving"
        agent.last_action = f"move:{next_tile.kind}"
        self._reserve_occupancy(occupied, next_position)

    def _consume_from_node(self, agent: SpatialAgent, node: SpatialNode) -> None:
        agent.path_length = 0
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

    def _update_agent(self, agent: SpatialAgent, occupied: dict[tuple[int, int], int]) -> None:
        if not agent.is_alive():
            agent.state = "dead"
            agent.target_id = None
            agent.target_kind = None
            agent.last_action = "dead"
            agent.path_length = None
            agent.move_cooldown = 0
            return

        agent.hunger = min(1.0, agent.hunger + 0.032)
        agent.thirst = min(1.0, agent.thirst + 0.041)
        if agent.hunger > 0.88:
            agent.health = max(0.0, agent.health - 0.016)
        if agent.thirst > 0.91:
            agent.health = max(0.0, agent.health - 0.022)
        if not agent.is_alive():
            agent.state = "dead"
            agent.target_id = None
            agent.target_kind = None
            agent.last_action = "dead"
            agent.path_length = None
            agent.move_cooldown = 0
            return

        target = self._choose_target(agent)
        agent.target_id = target.id
        agent.target_kind = target.kind

        if agent.move_cooldown > 0:
            agent.move_cooldown -= 1
            agent.state = "traversing"
            agent.last_action = f"traverse:{self._tile((agent.x, agent.y)).kind}"
            return

        if (agent.x, agent.y) == (target.x, target.y):
            self._consume_from_node(agent, target)
            return

        self._move_agent_toward(agent, target, occupied)

    def _record_metrics(self) -> None:
        alive_agents = [agent for agent in self.agents if agent.is_alive()]
        count = len(alive_agents)
        food = self._node_by_kind("food")
        water = self._node_by_kind("water")
        self.time_series["tick"].append(self.tick)
        self.time_series["population"].append(count)
        self.time_series["avg_health"].append(round(sum(agent.health for agent in alive_agents) / count, 4) if count else 0.0)
        self.time_series["avg_hunger"].append(round(sum(agent.hunger for agent in alive_agents) / count, 4) if count else 0.0)
        self.time_series["avg_thirst"].append(round(sum(agent.thirst for agent in alive_agents) / count, 4) if count else 0.0)
        self.time_series["moving_agents"].append(sum(1 for agent in alive_agents if agent.state in {"moving", "traversing"}))
        self.time_series["blocked_agents"].append(sum(1 for agent in alive_agents if agent.state in {"blocked", "waiting"}))
        self.time_series["food_stock"].append(round(food.stock, 4))
        self.time_series["water_stock"].append(round(water.stock, 4))

    def _record_snapshot(self, force: bool = False) -> None:
        if not force and self.tick % self.snapshot_frequency != 0:
            return
        self.snapshots.append(self.snapshot())

    def step(self) -> dict[str, Any]:
        self.tick += 1
        for node in self.nodes:
            node.stock = min(node.capacity, node.stock + node.replenish_per_tick)
        occupied = self._occupancy_counts()
        for agent in self.agents:
            self._update_agent(agent, occupied)
        self._record_metrics()
        self._record_snapshot()
        return self.snapshot()

    def run(self) -> dict[str, list[Any]]:
        while self.tick < self.config.days:
            self.step()
        return self.time_series

    def snapshot(self) -> dict[str, Any]:
        alive_agents = [agent for agent in self.agents if agent.is_alive()]
        occupied = self._occupancy_counts()
        selected_agent = max(self.agents, key=lambda agent: (agent.hunger + agent.thirst, agent.health), default=None)
        selected = selected_agent.as_dict() if selected_agent else None
        food = self._node_by_kind("food")
        water = self._node_by_kind("water")
        tiles = [
            tile.as_dict(occupied=occupied.get((tile.x, tile.y), 0))
            for tile in sorted(self.tiles.values(), key=lambda item: (item.y, item.x))
        ]
        return {
            "tick": self.tick,
            "grid": {
                "width": self.config.grid_width,
                "height": self.config.grid_height,
                "tile_size": 1,
                "tiles": tiles,
            },
            "nodes": [node.as_dict() for node in self.nodes],
            "agents": [agent.as_dict() for agent in self.agents],
            "metrics": {
                "population": len(alive_agents),
                "avg_health": round(sum(agent.health for agent in alive_agents) / len(alive_agents), 4) if alive_agents else 0.0,
                "avg_hunger": round(sum(agent.hunger for agent in alive_agents) / len(alive_agents), 4) if alive_agents else 0.0,
                "avg_thirst": round(sum(agent.thirst for agent in alive_agents) / len(alive_agents), 4) if alive_agents else 0.0,
                "moving_agents": sum(1 for agent in alive_agents if agent.state in {"moving", "traversing"}),
                "blocked_agents": sum(1 for agent in alive_agents if agent.state in {"blocked", "waiting"}),
                "food_stock": round(food.stock, 3),
                "water_stock": round(water.stock, 3),
            },
            "selected_agent": selected,
        }

    def build_artifact(self) -> SimulationArtifact:
        if not self.time_series["tick"] and self.tick == 0:
            self._record_metrics()
        return SimulationArtifact(
            metadata={
                "engine_version": SPATIAL_ENGINE_VERSION,
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
