# simLogger.py
import pandas as pd

class SimulationLogger:
    METRIC_SCHEMA = {
        "day": {"type": "int", "description": "1-indexed simulation day"},
        "total_food": {"type": "float", "description": "Food stored across all households"},
        "total_labor": {"type": "float", "description": "Total labor contributed on the day"},
        "population": {"type": "int", "description": "Alive members across all households"},
        "total_water": {"type": "float", "description": "Water stored across all households"},
        "rainfall": {"type": "float", "description": "Weather rainfall factor for the day"},
        "drought_factor": {"type": "float", "description": "Farm productivity multiplier for the day"},
        "avg_health": {"type": "float", "description": "Average health of living members"},
    }

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

    @classmethod
    def metric_schema(cls):
        return dict(cls.METRIC_SCHEMA)

    def to_dataframe(self):
        return pd.DataFrame(self.to_dict())
