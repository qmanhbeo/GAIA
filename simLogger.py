# simLogger.py
import matplotlib.pyplot as plt
import pandas as pd  # NEW

class SimulationLogger:
    def __init__(self):
        self.days = []
        self.total_food = []
        self.total_labor = []
        self.population = []
        self.total_water = []
        self.rainfall = []
        self.drought_factor = []
        self.avg_health = []  # NEW

    def record(self, day, households, labor, weather):
        self.days.append(day)
        self.total_food.append(sum(h.food for h in households))
        self.total_labor.append(labor)
        self.total_water.append(sum(h.water for h in households))
        alive_members = [m for h in households for m in h.members if m.is_alive()]
        self.population.append(len(alive_members))
        self.rainfall.append(weather.rainfall)
        self.drought_factor.append(weather.drought_factor)
        # NEW: average health of alive members (fallback to 0 if none)
        self.avg_health.append(
            sum(m.health for m in alive_members) / len(alive_members) if alive_members else 0.0
        )

    # keep your plot() if you like, but visualizer will do plotting

    # NEW: structured outputs for visualizer
    def to_dict(self):
        return {
            "day": self.days,
            "total_food": self.total_food,
            "total_labor": self.total_labor,
            "population": self.population,
            "total_water": self.total_water,
            "rainfall": self.rainfall,
            "drought_factor": self.drought_factor,
            "avg_health": self.avg_health,
        }

    def to_dataframe(self):
        return pd.DataFrame(self.to_dict())
