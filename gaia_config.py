from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from assumptions import DEFAULT_LEGACY_ASSUMPTIONS, LegacyAssumptions


LEGACY_MODE = "legacy_v0_2"


@dataclass(frozen=True)
class SimulationConfig:
    days: int = 300
    seed: int = 42
    num_households: int = 1
    members_per_household: int = 20
    mode: str = LEGACY_MODE
    snapshot_frequency: int = 0
    assumptions: LegacyAssumptions = field(default_factory=lambda: DEFAULT_LEGACY_ASSUMPTIONS)

    def __post_init__(self) -> None:
        positive_fields = {
            "days": self.days,
            "num_households": self.num_households,
            "members_per_household": self.members_per_household,
        }
        for name, value in positive_fields.items():
            if value < 1:
                raise ValueError(f"{name} must be >= 1")

        if self.snapshot_frequency < 0:
            raise ValueError("snapshot_frequency must be >= 0")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SimulationConfig":
        assumptions_payload = payload.get("assumptions")
        if isinstance(assumptions_payload, dict):
            payload = dict(payload)
            payload["assumptions"] = LegacyAssumptions.from_dict(assumptions_payload)
        return cls(**payload)
