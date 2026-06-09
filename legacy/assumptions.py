from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class LegacyAssumptions:
    # === Labor Eligibility ===
    MIN_WORKING_AGE: int = 15
    MAX_WORKING_AGE: int = 60

    # === Aging & Mortality ===
    MAX_AGE: int = 85
    DAILY_AGING: int = 1

    # === Hunger & Health ===
    HUNGER_INCREASE_PER_LABOR: float = 0.1
    HUNGER_THRESHOLD_FOR_DAMAGE: float = 1.0
    HEALTH_LOSS_FROM_STARVATION: float = 0.1

    # === Feeding ===
    FOOD_REQUIRED_PER_MEMBER_PER_DAY: float = 1.0
    FEED_ALL_OR_NONE: bool = True

    # === Reproduction ===
    REPRODUCTION_MIN_MEMBERS: int = 2
    REPRODUCTION_HUNGER_LIMIT: float = 0.5
    REPRODUCTION_CHANCE: float = 0.5

    # === Farm Output ===
    FARM_LABOR_NEEDED: float = 3.0
    FARM_BASE_OUTPUT: float = 10.0
    FARM_SURPLUS_EFFICIENCY: float = 0.5

    # === Food Distribution ===
    EQUAL_DISTRIBUTION: bool = True

    # === Hydration ===
    WATER_REQUIRED_PER_MEMBER_PER_DAY: float = 1.0
    DAILY_HYDRATION_DECAY: float = 0.1
    DEHYDRATION_THRESHOLD: float = 0.3
    HEALTH_LOSS_FROM_DEHYDRATION: float = 0.1

    # === Weather System ===
    BASE_RAINFALL: float = 0.6
    RAIN_AMPLITUDE: float = 0.4
    RAIN_CYCLE_DAYS: int = 30
    BASE_DROUGHT: float = 1.0
    DROUGHT_AMPLITUDE: float = 0.3
    STORM_PROBABILITY: float = 0.02

    # === Weather Randomization Parameters ===
    RAIN_AMP_FACTOR_RANGE: tuple[float, float] = (0.8, 1.2)
    RAIN_PHASE_SHIFT_RANGE: tuple[float, float] = (-0.25, 0.25)
    RAIN_NOISE_RANGE: tuple[float, float] = (-0.05, 0.05)
    DROUGHT_NOISE_RANGE: tuple[float, float] = (-0.05, 0.05)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "LegacyAssumptions":
        return cls(**payload)


DEFAULT_LEGACY_ASSUMPTIONS = LegacyAssumptions()


def apply_legacy_assumptions(values: LegacyAssumptions | dict[str, Any]) -> LegacyAssumptions:
    resolved = values if isinstance(values, LegacyAssumptions) else LegacyAssumptions.from_dict(values)
    for name, value in resolved.to_dict().items():
        globals()[name] = value
    return resolved


apply_legacy_assumptions(DEFAULT_LEGACY_ASSUMPTIONS)
