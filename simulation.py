# simulation.py
from household import Household
from farm import Farm
from water import WaterSource
from weather import Weather
from simLogger import SimulationLogger
from assumptions import MIN_WORKING_AGE, MAX_WORKING_AGE, EQUAL_DISTRIBUTION

class SimulationEngine:
    def __init__(self, num_households=1, members_per_household=50, days=200):
        self.households = [
            Household(name=f"Household_{i+1}", num_members=members_per_household)
            for i in range(num_households)
        ]
        self.farm = Farm(name="CommuneFarm")
        self.water_source = WaterSource()
        self.logger = SimulationLogger()
        self.days = days

    def run_day(self, day):
        weather = Weather(day)

        # Gather labor
        labor = 0
        for h in self.households:
            for m in h.members:
                if m.is_alive() and MIN_WORKING_AGE <= m.age <= MAX_WORKING_AGE:
                    labor += m.labor()

        # Farm productivity (weather-adjusted)
        produced = self.farm.run_day(labor, drought_factor=weather.drought_factor)

        # Distribute food equally
        harvested = self.farm.harvest()
        if EQUAL_DISTRIBUTION:
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

    def run(self):
        for day in range(1, self.days + 1):
            self.run_day(day)
        # DO NOT plot here; visualizer handles it
        return self.logger.to_dict()

    # Make sure these are INSIDE the class (correct indentation)
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
