from assumptions import (
    FARM_LABOR_NEEDED,
    FARM_BASE_OUTPUT,
    FARM_SURPLUS_EFFICIENCY,
)

class Farm:
    def __init__(self, name="Farm"):
        self.name = name
        self.labor_needed = FARM_LABOR_NEEDED
        self.base_output = FARM_BASE_OUTPUT
        self.storage = 0.0

    def run_day(self, labor_input, drought_factor=1.0):  # 🌦️ Add drought_factor
        if labor_input <= 0:
            produced = 0.0
        elif labor_input < self.labor_needed:
            produced = self.base_output * (labor_input / self.labor_needed)
        else:
            surplus = labor_input - self.labor_needed
            produced = self.base_output + (FARM_SURPLUS_EFFICIENCY * surplus)

        produced *= drought_factor  # 🌾 Scale final output
        self.storage += produced
        return produced

    def harvest(self, amount=None):
        if amount is None or amount > self.storage:
            amount = self.storage
        self.storage -= amount
        return amount
