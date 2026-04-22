# simulation.py
from __future__ import annotations

import random

import numpy as np

import assumptions
from assumptions import apply_legacy_assumptions
from gaia_config import LEGACY_MODE, SimulationConfig
from household import Household
from farm import Farm
from water import WaterSource
from weather import Weather
from simLogger import SimulationLogger
from simulation_artifact import SimulationArtifact


class SimulationEngine:
    def __init__(
        self,
        config: SimulationConfig | None = None,
        *,
        num_households=1,
        members_per_household=50,
        days=200,
        seed=42,
    ):
        self.config = config or SimulationConfig(
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
