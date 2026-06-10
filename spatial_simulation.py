from __future__ import annotations

from dataclasses import dataclass, field
from heapq import heappop, heappush
from typing import Any

from gaia_config import SPATIAL_MODE, SimulationConfig
from simulation_artifact import SimulationArtifact
from rules.decision import DecisionRule
from rules.resources import ResourceRule


SPATIAL_ENGINE_VERSION = "spatial-v1d-food-carrying"
HOME_STARTING_FOOD = 2.0
HOME_FOOD_CAPACITY = 10.0
CAMP_CAPACITY = 2.0
CAMP_COLOR = "#cd853f"
CAMP_SHELTER_QUALITY_DEFAULT = 0.0
AGENT_CARRY_CAPACITY = 1.0
HOME_MEAL_SIZE = 0.25
HOME_MEAL_HUNGER_RELIEF = 0.58
NODE_MEAL_SIZE = 0.22
NODE_MEAL_HUNGER_RELIEF = 0.62
GATHER_AMOUNT = 1.0
HUNGER_HOME_THRESHOLD = 0.5
STARVING_HUNGER_THRESHOLD = 0.82
THIRST_WATER_THRESHOLD = 0.86


@dataclass
class SimulationClock:
    tick: int = 0
    tick_duration: str = "1 hour"

    def advance(self, ticks: int = 1) -> None:
        self.tick += ticks

    @property
    def elapsed_time(self) -> str:
        if self.tick == 1:
            return "1 hour"
        return f"{self.tick} hours"

    def as_dict(self) -> dict[str, Any]:
        return {
            "tick": self.tick,
            "tick_duration": self.tick_duration,
            "elapsed_time": self.elapsed_time,
            "elapsed_hours": self.tick,
        }


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
    shelter_quality: float = 0.0
    rest_safety: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        stock = round(self.stock, 3)
        capacity = round(self.capacity, 3)
        payload = {
            "id": self.id,
            "type": "resource_node" if self.kind in {"food", "water"} else "place",
            "parent_id": None,
            "kind": self.kind,
            "label": self.label,
            "x": self.x,
            "y": self.y,
            "position": {"x": self.x, "y": self.y},
            "stock": stock,
            "capacity": capacity,
            "stock_ratio": round(self.stock / self.capacity, 3) if self.capacity else 0.0,
            "components": {
                "resource": {
                    "kind": self.kind,
                    "stock": stock,
                    "capacity": capacity,
                }
            },
            "color": self.color,
        }
        if self.kind == "home":
            payload["stored_food"] = stock
            payload["stored_food_capacity"] = capacity
            payload["components"]["storage"] = {
                "stored_food": stock,
                "stored_food_capacity": capacity,
            }
        if self.kind == "camp":
            payload["shelter_quality"] = round(self.shelter_quality, 3)
        payload["rest_safety"] = round(self.rest_safety, 3)
        return payload


def make_camp_node(
    id: str,
    x: int,
    y: int,
    label: str | None = None,
    shelter_quality: float = CAMP_SHELTER_QUALITY_DEFAULT,
) -> SpatialNode:
    return SpatialNode(
        id=id,
        kind="camp",
        label=label or id,
        x=x,
        y=y,
        stock=0.0,
        capacity=CAMP_CAPACITY,
        replenish_per_tick=0.0,
        color=CAMP_COLOR,
        shelter_quality=shelter_quality,
    rest_safety=shelter_quality,
    )


@dataclass
class SpatialAgent:
    id: str
    label: str
    parent_id: str | None
    home_id: str
    x: int
    y: int
    home_x: int
    home_y: int
    hunger: float
    thirst: float
    health: float
    fatigue: float = 0.0  # aggregate bodily/rest debt; not yet split into physical/mental/vigilance fatigue
    exposure: float = 0.0  # accumulated environmental burden; not yet decomposed into heat/cold/wet
    carried_food: float = 0.0
    carry_capacity: float = AGENT_CARRY_CAPACITY
    state: str = "idle"
    target_id: str | None = None
    target_kind: str | None = None
    last_action: str = "spawned"
    move_cooldown: int = 0
    path_length: int | None = None
    current_task: str | None = None
    task_target_id: str | None = None
    task_started_tick: int | None = None
    node_memory: dict[str, Any] = field(default_factory=dict)

    def is_alive(self) -> bool:
        return self.health > 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": "person",
            "parent_id": self.parent_id,
            "home_id": self.home_id,
            "label": self.label,
            "x": self.x,
            "y": self.y,
            "position": {"x": self.x, "y": self.y},
            "home_x": self.home_x,
            "home_y": self.home_y,
            "hunger": round(self.hunger, 3),
            "thirst": round(self.thirst, 3),
            "fatigue": round(self.fatigue, 3),
            "exposure": round(self.exposure, 3),
            "health": round(self.health, 3),
            "carried_food": round(self.carried_food, 3),
            "carry_capacity": round(self.carry_capacity, 3),
            "state": self.state,
            "target_id": self.target_id,
            "target_kind": self.target_kind,
            "last_action": self.last_action,
            "move_cooldown": self.move_cooldown,
            "path_length": self.path_length,
            "current_task": self.current_task,
            "task_target_id": self.task_target_id,
            "task_started_tick": self.task_started_tick,
            "node_memory": {
                node_id: {
                    "kind": entry["kind"],
                    "label": entry["label"],
                    "x": entry["x"],
                    "y": entry["y"],
                    "last_seen_stock": round(entry["last_seen_stock"], 3),
                    "last_seen_capacity": round(entry["last_seen_capacity"], 3),
                    "last_seen_tick": entry["last_seen_tick"],
                }
                for node_id, entry in self.node_memory.items()
            },
            "components": {
                "needs": {
                    "hunger": round(self.hunger, 3),
                    "thirst": round(self.thirst, 3),
                    "fatigue": round(self.fatigue, 3),
                },
                "health": {"value": round(self.health, 3)},
                "inventory": {
                    "carried_food": round(self.carried_food, 3),
                    "carry_capacity": round(self.carry_capacity, 3),
                },
                "movement": {
                    "state": self.state,
                    "target_id": self.target_id,
                    "target_kind": self.target_kind,
                    "path_length": self.path_length,
                },
            },
        }


class SpatialPrototypeEngine:
    def __init__(self, config: SimulationConfig):
        self.config = config
        self.clock = SimulationClock(tick_duration=config.tick_duration)
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
            "avg_fatigue": [],
            "max_fatigue": [],
            "avg_exposure": [],
            "max_exposure": [],
            "resting_count": [],
            "seeking_rest_count": [],
            "fatigued_count": [],
            "moving_agents": [],
            "blocked_agents": [],
            "food_stock": [],
            "total_home_food": [],
            "water_stock": [],
        }
        self.snapshots: list[dict[str, Any]] = []
        self.decision_rule = DecisionRule(
            hunger_home_threshold=HUNGER_HOME_THRESHOLD,
            home_meal_size=HOME_MEAL_SIZE,
            thirst_water_threshold=THIRST_WATER_THRESHOLD,
            hunger_critical=config.physiology.hunger_damage_threshold,
            thirst_critical=config.physiology.thirst_damage_threshold,
        )
        self.resource_rule = ResourceRule()
        self.events: list[dict[str, Any]] = []
        self.event_log: list[dict[str, Any]] = []
        self._record_snapshot(force=True)

    @property
    def tick(self) -> int:
        return self.clock.tick

    @tick.setter
    def tick(self, value: int) -> None:
        self.clock.tick = value

    def _barrier_x(self) -> int | None:
        if self.config.grid_width < 10:
            return None
        return max(4, self.config.grid_width // 2 - 2)

    def _gap_y(self) -> int | None:
        if self._barrier_x() is None or self.config.grid_height < 6:
            return None
        return max(1, min(self.config.grid_height - 2, self.config.grid_height // 2 - 1))

    def _build_nodes(self) -> list[SpatialNode]:
        width = self.config.grid_width
        height = self.config.grid_height
        food_x, food_y = self.config.layout.food_node_position(width, height)
        water_x, water_y = self.config.layout.water_node_position(width, height)

        nodes = []
        for index in range(self.config.num_households):
            home_x, home_y = self.config.layout.home_position(index, width, height)
            nodes.append(
                SpatialNode(
                    id=f"home-{index + 1}",
                    kind="home",
                    label=f"Home {index + 1}",
                    x=home_x,
                    y=home_y,
                    stock=HOME_STARTING_FOOD,
                    capacity=HOME_FOOD_CAPACITY,
                    replenish_per_tick=0.0,
                    color="#ffdd9a",
                    rest_safety=1.0,
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
                        parent_id=home.id,
                        home_id=home.id,
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

    def _home_for_agent(self, agent: SpatialAgent) -> SpatialNode:
        for node in self.nodes:
            if node.id == agent.home_id:
                return node
        return self._node_by_kind("home", preferred_home=(agent.home_x, agent.home_y))

    @staticmethod
    def _observe_node(agent: SpatialAgent, node: SpatialNode, tick: int) -> None:
        agent.node_memory[node.id] = {
            "kind": node.kind,
            "label": node.label,
            "x": node.x,
            "y": node.y,
            "last_seen_stock": node.stock,
            "last_seen_capacity": node.capacity,
            "last_seen_tick": tick,
        }

    def _nearby_agents(self, agent: SpatialAgent, radius: int = 1) -> list[SpatialAgent]:
        """Return alive agents within Manhattan distance <= radius, including self."""
        result: list[SpatialAgent] = []
        ax, ay = agent.x, agent.y
        for other in self.agents:
            if not other.is_alive():
                continue
            if abs(other.x - ax) + abs(other.y - ay) <= radius:
                result.append(other)
        return result

    def _effective_rest_quality(self, agent: SpatialAgent, node: SpatialNode) -> float:
        """Rest quality at node, considering node safety and nearby others."""
        phys = self.config.physiology
        nearby_others = max(0, len(self._nearby_agents(agent)) - 1)
        return min(
            1.0,
            node.rest_safety + phys.group_rest_safety_bonus_per_nearby_agent * nearby_others,
        )

    def _apply_base_fatigue(self, agent: SpatialAgent) -> None:
        phys = self.config.physiology
        agent.fatigue = min(1.0, agent.fatigue + phys.fatigue_increase_per_tick)

    def _apply_movement_fatigue(self, agent: SpatialAgent) -> None:
        phys = self.config.physiology
        gain = phys.movement_fatigue_per_step
        if agent.carry_capacity > 0:
            load_ratio = max(0.0, min(1.0, agent.carried_food / agent.carry_capacity))
        else:
            load_ratio = 0.0
        gain += phys.carrying_fatigue_per_step_at_full_load * load_ratio
        agent.fatigue = min(1.0, agent.fatigue + gain)

    def _apply_exposure(self, agent: SpatialAgent) -> None:
        phys = self.config.physiology
        home = self._home_for_agent(agent)
        if (agent.x, agent.y) == (home.x, home.y):
            agent.exposure = max(0.0, agent.exposure - phys.exposure_recovery_per_tick_at_home)
        else:
            agent.exposure = min(1.0, agent.exposure + phys.exposure_increase_per_tick_away_from_home)

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

    def _move_agent_toward(
        self,
        agent: SpatialAgent,
        node: SpatialNode,
        occupied: dict[tuple[int, int], int],
        travel_state: str,
    ) -> bool:
        current = (agent.x, agent.y)
        goal = (node.x, node.y)
        self._release_occupancy(occupied, current)
        path = self._find_path(current, goal, occupied)
        if not path or len(path) < 2:
            self._reserve_occupancy(occupied, current)
            agent.state = "blocked"
            agent.last_action = f"blocked:{node.kind}"
            agent.path_length = None
            return False

        next_position = path[1]
        next_tile = self._tile(next_position)
        if occupied.get(next_position, 0) >= next_tile.occupancy_limit:
            self._reserve_occupancy(occupied, current)
            agent.state = "waiting"
            agent.last_action = f"wait:occupied:{node.kind}"
            agent.path_length = len(path) - 1
            return False

        agent.x, agent.y = next_position
        agent.move_cooldown = max(0, next_tile.movement_cost - 1)
        agent.path_length = len(path) - 1
        agent.state = travel_state
        agent.last_action = f"move:{next_tile.kind}"
        self._reserve_occupancy(occupied, next_position)
        return True

    def _consume_from_node(self, agent: SpatialAgent, node: SpatialNode) -> None:
        agent.path_length = 0
        if node.kind == "food":
            home = self._home_for_agent(agent)
            if agent.hunger >= STARVING_HUNGER_THRESHOLD and node.stock >= NODE_MEAL_SIZE:
                node.stock = max(0.0, node.stock - NODE_MEAL_SIZE)
                agent.hunger = max(0.0, agent.hunger - NODE_MEAL_HUNGER_RELIEF)
                agent.state = "eating_at_node"
                agent.last_action = "eat_at_node"
                self._record_event("eat_at_node", agent=agent, node=node, amount=NODE_MEAL_SIZE)
                agent.current_task = None
                agent.task_target_id = None
            elif agent.carried_food < agent.carry_capacity and home.stock < home.capacity and node.stock > 0:
                amount = min(GATHER_AMOUNT, agent.carry_capacity - agent.carried_food, home.capacity - home.stock, node.stock)
                node.stock = max(0.0, node.stock - amount)
                agent.carried_food += amount
                agent.state = "gathering_food"
                agent.last_action = "gather_food"
                self._record_event("gather_food", agent=agent, node=node, amount=amount)
                agent.current_task = "return_home_with_food"
                agent.task_target_id = home.id
            elif node.stock >= NODE_MEAL_SIZE and agent.hunger >= HUNGER_HOME_THRESHOLD:
                node.stock = max(0.0, node.stock - NODE_MEAL_SIZE)
                agent.hunger = max(0.0, agent.hunger - NODE_MEAL_HUNGER_RELIEF)
                agent.state = "eating_at_node"
                agent.last_action = "eat_at_node"
                self._record_event("eat_at_node", agent=agent, node=node, amount=NODE_MEAL_SIZE)
                agent.current_task = None
                agent.task_target_id = None
            else:
                agent.state = "waiting"
                agent.last_action = "wait:food"
        elif node.kind == "water":
            if node.stock >= 0.22:
                node.stock = max(0.0, node.stock - 0.22)
                agent.thirst = max(0.0, agent.thirst - 0.74)
                agent.state = "drinking"
                agent.last_action = "drink"
                self._record_event("drink", agent=agent, node=node, amount=0.22)
                agent.current_task = None
                agent.task_target_id = None
            else:
                agent.state = "waiting"
                agent.last_action = "wait:water"
        else:
            self._handle_home_arrival(agent, node)

    def _handle_home_arrival(self, agent: SpatialAgent, home: SpatialNode) -> None:
        phys = self.config.physiology
        agent.path_length = 0
        if agent.carried_food > 0 and home.stock < home.capacity:
            amount = min(agent.carried_food, home.capacity - home.stock)
            home.stock += amount
            agent.carried_food -= amount
            agent.state = "depositing_food"
            agent.last_action = "deposit_food"
            self._record_event("deposit_food", agent=agent, node=home, amount=amount)
            agent.current_task = None
            agent.task_target_id = None
            return
        if agent.hunger >= HUNGER_HOME_THRESHOLD and home.stock >= HOME_MEAL_SIZE:
            home.stock = max(0.0, home.stock - HOME_MEAL_SIZE)
            agent.hunger = max(0.0, agent.hunger - HOME_MEAL_HUNGER_RELIEF)
            agent.state = "eating_at_home"
            agent.last_action = "eat_at_home"
            self._record_event("eat_at_home", agent=agent, node=home, amount=HOME_MEAL_SIZE)
            agent.current_task = None
            agent.task_target_id = None
            return
        agent.health = min(1.0, agent.health + phys.home_health_regen_per_tick)
        recovery = phys.fatigue_recovery_per_tick * self._effective_rest_quality(agent, home)
        agent.fatigue = max(0.0, agent.fatigue - recovery)
        agent.current_task = None
        agent.task_target_id = None
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
            agent.current_task = None
            agent.task_target_id = None
            agent.task_started_tick = None
            return

        phys = self.config.physiology
        agent.hunger = min(1.0, agent.hunger + phys.hunger_increase_per_tick)
        agent.thirst = min(1.0, agent.thirst + phys.thirst_increase_per_tick)
        self._apply_base_fatigue(agent)
        self._apply_exposure(agent)
        if agent.hunger > phys.hunger_damage_threshold:
            agent.health = max(0.0, agent.health - phys.hunger_damage_rate)
        if agent.thirst > phys.thirst_damage_threshold:
            agent.health = max(0.0, agent.health - phys.thirst_damage_rate)
        if not agent.is_alive():
            agent.state = "dead"
            agent.target_id = None
            agent.target_kind = None
            agent.last_action = "dead"
            agent.path_length = None
            agent.move_cooldown = 0
            self._record_event("agent_died", agent=agent)
            agent.current_task = None
            agent.task_target_id = None
            agent.task_started_tick = None
            return

        target, travel_state = self.decision_rule.choose_plan(self, agent)
        agent.target_id = target.id
        agent.target_kind = target.kind

        if agent.move_cooldown > 0:
            agent.move_cooldown -= 1
            agent.state = travel_state
            agent.last_action = f"traverse:{self._tile((agent.x, agent.y)).kind}"
            return

        if (agent.x, agent.y) == (target.x, target.y):
            self._consume_from_node(agent, target)
        else:
            moved = self._move_agent_toward(agent, target, occupied, travel_state)
            if moved:
                self._apply_movement_fatigue(agent)

        for node in self.nodes:
            if (agent.x, agent.y) == (node.x, node.y):
                self._observe_node(agent, node, self.tick)

    def _record_metrics(self) -> None:
        alive_agents = [agent for agent in self.agents if agent.is_alive()]
        count = len(alive_agents)
        food = self._node_by_kind("food")
        water = self._node_by_kind("water")
        home_food = sum(node.stock for node in self.nodes if node.kind == "home")
        self.time_series["tick"].append(self.tick)
        self.time_series["population"].append(count)
        self.time_series["avg_health"].append(round(sum(agent.health for agent in alive_agents) / count, 4) if count else 0.0)
        self.time_series["avg_hunger"].append(round(sum(agent.hunger for agent in alive_agents) / count, 4) if count else 0.0)
        self.time_series["avg_thirst"].append(round(sum(agent.thirst for agent in alive_agents) / count, 4) if count else 0.0)
        self.time_series["avg_fatigue"].append(round(sum(agent.fatigue for agent in alive_agents) / count, 4) if count else 0.0)
        self.time_series["max_fatigue"].append(round(max(agent.fatigue for agent in alive_agents), 4) if count else 0.0)
        self.time_series["avg_exposure"].append(round(sum(agent.exposure for agent in alive_agents) / count, 4) if count else 0.0)
        self.time_series["max_exposure"].append(round(max(agent.exposure for agent in alive_agents), 4) if count else 0.0)
        self.time_series["resting_count"].append(sum(1 for agent in alive_agents if agent.last_action == "rest"))
        self.time_series["seeking_rest_count"].append(sum(1 for agent in alive_agents if agent.current_task == "seek_rest"))
        threshold = self.config.physiology.fatigue_rest_threshold
        self.time_series["fatigued_count"].append(sum(1 for agent in alive_agents if agent.fatigue >= threshold))
        self.time_series["moving_agents"].append(
            sum(1 for agent in alive_agents if agent.state in {"seeking_food", "carrying_food_home", "seeking_home_food", "seeking_water"})
        )
        self.time_series["blocked_agents"].append(sum(1 for agent in alive_agents if agent.state in {"blocked", "waiting"}))
        self.time_series["food_stock"].append(round(food.stock, 4))
        self.time_series["total_home_food"].append(round(home_food, 4))
        self.time_series["water_stock"].append(round(water.stock, 4))

    def _record_snapshot(self, force: bool = False) -> None:
        if not force and self.tick % self.snapshot_frequency != 0:
            return
        self.snapshots.append(self.snapshot())

    def _record_event(self, event: str, agent: SpatialAgent | None = None, node: SpatialNode | None = None, amount: float | None = None) -> None:
        entry: dict[str, Any] = {"tick": self.tick, "event": event}
        if agent is not None:
            entry["agent_id"] = agent.id
            entry["agent_label"] = agent.label
        if node is not None:
            entry["node_id"] = node.id
            entry["node_kind"] = node.kind
        if amount is not None:
            entry["amount"] = round(amount, 4)
        self.events.append(entry)
        self.event_log.append(entry)
        if len(self.event_log) > 200:
            self.event_log = self.event_log[-200:]

    def step(self) -> dict[str, Any]:
        self.clock.advance()
        self.events.clear()
        self.resource_rule.apply(self)
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
        food_stock = round(sum(node.stock for node in self.nodes if node.kind == "food"), 3)
        total_home_food = round(sum(node.stock for node in self.nodes if node.kind == "home"), 3)
        home_storage_capacity = round(sum(node.capacity for node in self.nodes if node.kind == "home"), 3)
        water_stock = round(sum(node.stock for node in self.nodes if node.kind == "water"), 3)
        tiles = [
            tile.as_dict(occupied=occupied.get((tile.x, tile.y), 0))
            for tile in sorted(self.tiles.values(), key=lambda item: (item.y, item.x))
        ]
        metrics = {
            "population": len(alive_agents),
            "avg_health": round(sum(agent.health for agent in alive_agents) / len(alive_agents), 4) if alive_agents else 0.0,
            "avg_hunger": round(sum(agent.hunger for agent in alive_agents) / len(alive_agents), 4) if alive_agents else 0.0,
            "avg_thirst": round(sum(agent.thirst for agent in alive_agents) / len(alive_agents), 4) if alive_agents else 0.0,
            "avg_fatigue": round(sum(agent.fatigue for agent in alive_agents) / len(alive_agents), 4) if alive_agents else 0.0,
            "max_fatigue": round(max(agent.fatigue for agent in alive_agents), 4) if alive_agents else 0.0,
            "avg_exposure": round(sum(agent.exposure for agent in alive_agents) / len(alive_agents), 4) if alive_agents else 0.0,
            "max_exposure": round(max(agent.exposure for agent in alive_agents), 4) if alive_agents else 0.0,
            "resting_count": sum(1 for agent in alive_agents if agent.last_action == "rest"),
            "seeking_rest_count": sum(1 for agent in alive_agents if agent.current_task == "seek_rest"),
            "fatigued_count": sum(1 for agent in alive_agents if agent.fatigue >= self.config.physiology.fatigue_rest_threshold),
            "moving_agents": sum(1 for agent in alive_agents if agent.state in {"moving", "traversing"}),
            "blocked_agents": sum(1 for agent in alive_agents if agent.state in {"blocked", "waiting"}),
            "food_stock": food_stock,
            "food_node_stock": food_stock,
            "total_home_food": total_home_food,
            "home_storage_capacity": home_storage_capacity,
            "water_stock": water_stock,
        }
        return {
            "tick": self.tick,
            "clock": self.clock.as_dict(),
            "population": metrics["population"],
            "food_stock": metrics["food_stock"],
            "food_node_stock": metrics["food_node_stock"],
            "total_home_food": metrics["total_home_food"],
            "home_storage_capacity": metrics["home_storage_capacity"],
            "water_stock": metrics["water_stock"],
            "avg_hunger": metrics["avg_hunger"],
            "avg_thirst": metrics["avg_thirst"],
            "avg_fatigue": metrics["avg_fatigue"],
            "max_fatigue": metrics["max_fatigue"],
            "avg_exposure": metrics["avg_exposure"],
            "max_exposure": metrics["max_exposure"],
            "tiles": tiles,
            "grid": {
                "width": self.config.grid_width,
                "height": self.config.grid_height,
                "tile_size": 1,
                "tiles": tiles,
            },
            "nodes": [node.as_dict() for node in self.nodes],
            "agents": [agent.as_dict() for agent in self.agents],
            "metrics": metrics,
            "selected_agent": selected,
            "events": list(self.events),
            "event_log": list(self.event_log),
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
                "tick_duration": self.config.tick_duration,
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
