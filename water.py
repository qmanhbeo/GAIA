class WaterSource:
    def __init__(self, daily_capacity=1000):
        self.base_capacity = daily_capacity  # Renamed to emphasize it's unchanging

    def distribute(self, households, rainfall=1.0):
        if not households:
            return

        adjusted_capacity = self.base_capacity * rainfall
        share = adjusted_capacity / len(households)

        for h in households:
            h.water += share
