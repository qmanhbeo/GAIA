from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


SPATIAL_MODE = "spatial_v1_prototype"


@dataclass(frozen=True)
class SpatialLayoutConfig:
    """Sandbox starting layout; rules stay in the engine, not in this config."""

    home_positions: tuple[tuple[int, int], ...]
    food_position: tuple[int, int]
    water_position: tuple[int, int]

    def __post_init__(self) -> None:
        if not self.home_positions:
            raise ValueError("home_positions must contain at least one position")

    @staticmethod
    def _coerce_position(position: Any) -> tuple[int, int]:
        x, y = position
        return int(x), int(y)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SpatialLayoutConfig":
        return cls(
            home_positions=tuple(cls._coerce_position(position) for position in payload["home_positions"]),
            food_position=cls._coerce_position(payload["food_position"]),
            water_position=cls._coerce_position(payload["water_position"]),
        )

    def clamped_position(self, position: tuple[int, int], grid_width: int, grid_height: int) -> tuple[int, int]:
        x, y = position
        return min(max(0, x), grid_width - 1), min(max(0, y), grid_height - 1)

    def home_position(self, index: int, grid_width: int, grid_height: int) -> tuple[int, int]:
        position = self.home_positions[min(index, len(self.home_positions) - 1)]
        return self.clamped_position(position, grid_width, grid_height)

    def food_node_position(self, grid_width: int, grid_height: int) -> tuple[int, int]:
        return self.clamped_position(self.food_position, grid_width, grid_height)

    def water_node_position(self, grid_width: int, grid_height: int) -> tuple[int, int]:
        return self.clamped_position(self.water_position, grid_width, grid_height)


@dataclass(frozen=True)
class ViewerConfig:
    """Display-only sandbox defaults; simulation time/rules are independent."""

    default_speed: float = 2.0


DEFAULT_LAYOUT = SpatialLayoutConfig(
    home_positions=((2, 8), (2, 5), (2, 11)),
    food_position=(12, 5),
    water_position=(20, 10),
)
DEFAULT_VIEWER = ViewerConfig()
DEFAULT_VIEWER_SPEED = DEFAULT_VIEWER.default_speed


@dataclass(frozen=True)
class SimulationConfig:
    days: int = 300
    seed: int = 42
    num_households: int = 1
    members_per_household: int = 20
    mode: str = SPATIAL_MODE
    snapshot_frequency: int = 0
    grid_width: int = 24
    grid_height: int = 16
    tick_duration: str = "1 hour"
    layout: SpatialLayoutConfig = field(default_factory=lambda: DEFAULT_LAYOUT)
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        positive_fields = {
            "days": self.days,
            "num_households": self.num_households,
            "members_per_household": self.members_per_household,
            "grid_width": self.grid_width,
            "grid_height": self.grid_height,
        }
        for name, value in positive_fields.items():
            if value < 1:
                raise ValueError(f"{name} must be >= 1")

        if self.snapshot_frequency < 0:
            raise ValueError("snapshot_frequency must be >= 0")

        if self.mode != SPATIAL_MODE:
            raise ValueError(f"active GAIA config only supports mode={SPATIAL_MODE!r}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SimulationConfig":
        allowed = set(cls.__dataclass_fields__)
        values = {key: value for key, value in payload.items() if key in allowed}
        if isinstance(values.get("layout"), dict):
            values["layout"] = SpatialLayoutConfig.from_dict(values["layout"])
        ignored = {key: value for key, value in payload.items() if key not in allowed}
        if ignored:
            extra = dict(values.get("extra") or {})
            extra.update(ignored)
            values["extra"] = extra
        return cls(**values)
