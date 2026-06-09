import random
import uuid

from . import assumptions

class Member:
    def __init__(self, name=None, age=None, gender=None):
        self.id = str(uuid.uuid4())
        self.name = name or f"Person_{random.randint(1000, 9999)}"
        self.age = age if age is not None else random.randint(15, 60)
        self.gender = gender or random.choice(["male", "female"])

        self.health = 1.0       # 0 = dead, 1 = full health
        self.hunger = 0.0       # 0 = full, 1 = starving
        self.hydration = 1.0    # 0 = dehydrated, 1 = fully hydrated

    def is_alive(self):
        return self.health > 0

    def labor(self):
        """Performs labor and increases hunger"""
        if not self.is_alive():
            return 0
        self.hunger += assumptions.HUNGER_INCREASE_PER_LABOR
        return round(self.health, 2)

    def consume(self, food=1.0):
        """Reduces hunger"""
        self.hunger = max(0.0, self.hunger - food)

    def drink(self, amount=1.0):
        """Reduces thirst"""
        self.hydration = min(1.0, self.hydration + amount)

    def dehydrate(self):
        """Hydration decay and health penalty from dehydration"""
        self.hydration -= assumptions.DAILY_HYDRATION_DECAY
        if self.hydration < assumptions.DEHYDRATION_THRESHOLD:
            self.health -= assumptions.HEALTH_LOSS_FROM_DEHYDRATION
        if self.health < 0:
            self.health = 0

    def deteriorate(self):
        """Aging and hunger-related health decay"""
        self.age += assumptions.DAILY_AGING
        if self.age >= assumptions.MAX_AGE:
            self.health = 0

        if self.hunger > assumptions.HUNGER_THRESHOLD_FOR_DAMAGE:
            self.health -= assumptions.HEALTH_LOSS_FROM_STARVATION

        self.dehydrate()  # now includes hydration decay

        if self.health < 0:
            self.health = 0

    def __repr__(self):
        return (
            f"<{self.name} ({self.gender}, {int(self.age)}) "
            f"Hunger:{self.hunger:.2f} Hydration:{self.hydration:.2f} HP:{self.health:.2f}>"
        )
