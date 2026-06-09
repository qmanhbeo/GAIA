# simulation.py
from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

from . import assumptions
from .assumptions import DEFAULT_LEGACY_ASSUMPTIONS, LegacyAssumptions, apply_legacy_assumptions
from .farm import Farm
from .household import Household
from .simLogger import SimulationLogger
from .water import WaterSource
from .weather import Weather
from simulation_artifact import SimulationArtifact


LEGACY_MODE = "legacy_v0_2"


@dataclass(frozen=True)
class LegacySimulationConfig:
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
    def from_dict(cls, payload: dict[str, Any]) -> "LegacySimulationConfig":
        values = dict(payload)
        assumptions_payload = values.get("assumptions")
        if isinstance(assumptions_payload, dict):
            values["assumptions"] = LegacyAssumptions.from_dict(assumptions_payload)
        return cls(**values)


class SimulationEngine:
    def __init__(
        self,
        config: LegacySimulationConfig | None = None,
        *,
        num_households=1,
        members_per_household=50,
        days=200,
        seed=42,
    ):
        self.config = config or LegacySimulationConfig(
            days=days,
            seed=seed,
            num_households=num_households,
            members_per_household=members_per_household,
            mode=LEGACY_MODE,
        )
        apply_legacy_assumptions(self.config.assumptions)
        self._seed_random_generators(self.config.seed)
        self.households = [
            Household(name=f"Household_{i+1}", num_members=self.config.members_per_household)
            for i in range(self.config.num_households)
        ]
        self.farm = Farm(name="CommuneFarm")
        self.water_source = WaterSource()
        self.logger = SimulationLogger()
        self.days = self.config.days
        self.snapshots = []

    @staticmethod
    def _seed_random_generators(seed):
        random.seed(seed)
        np.random.seed(seed)

    def run_day(self, day):
        weather = Weather(day)

        # Gather labor
        labor = 0
        for h in self.households:
            for m in h.members:
                if m.is_alive() and assumptions.MIN_WORKING_AGE <= m.age <= assumptions.MAX_WORKING_AGE:
                    labor += m.labor()

        # Farm productivity (weather-adjusted)
        produced = self.farm.run_day(labor, drought_factor=weather.drought_factor)

        # Distribute food equally
        harvested = self.farm.harvest()
        if assumptions.EQUAL_DISTRIBUTION:
            share = harvested / len(self.households)
            for h in self.households:
                h.food += share

        # Distribute water by rainfall
        self.water_source.distribute(self.households, rainfall=weather.rainfall)

        # Member & household updates
        for h in self.households:
            for m in h.members:
                m.deteriorate()
            h.feed()
            h.hydrate()
            h.maybe_reproduce()

        # Record metrics
        self.logger.record(day, self.households, labor, weather)
        self._record_snapshot(day)

    def run(self):
        start_day = (self.logger.days[-1] + 1) if self.logger.days else 1
        for day in range(start_day, self.days + 1):
            self.run_day(day)
        # DO NOT plot here; visualizer handles it
        return self.logger.to_dict()

    def build_artifact(self):
        return SimulationArtifact(
            metadata={
                "engine_version": "v0.2-legacy-baseline",
                "mode": self.config.mode,
                "seed": self.config.seed,
                "config": self.config.to_dict(),
                "metric_schema": self.logger.metric_schema(),
            },
            time_series=self.logger.to_dict(),
            final_state=self.snapshot(),
            snapshots=list(self.snapshots),
        )

    def run_artifact(self):
        if len(self.logger.days) < self.days:
            self.run()
        return self.build_artifact()

    def _record_snapshot(self, day):
        if self.config.snapshot_frequency <= 0:
            return
        if day % self.config.snapshot_frequency == 0:
            self.snapshots.append(self.snapshot())

    def snapshot(self):
        return {
            "day": len(self.logger.days) if self.logger.days else 0,
            "food": sum(h.food for h in self.households),
            "water": sum(h.water for h in self.households),
            "population": sum(1 for h in self.households for m in h.members if m.is_alive()),
            "labor_last": self.logger.total_labor[-1] if self.logger.total_labor else 0,
            "rainfall_last": self.logger.rainfall[-1] if self.logger.rainfall else 0,
        }

    def step(self):
        day = (self.logger.days[-1] + 1) if self.logger.days else 1
        self.run_day(day)
        return self.snapshot()
