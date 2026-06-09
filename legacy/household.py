import random

from . import assumptions
from .member import Member

class Household:
    def __init__(self, name=None, num_members=3):
        self.name = name or f"Household_{random.randint(1000, 9999)}"
        self.members = [Member() for _ in range(num_members)]
        self.food = 0.0
        self.water = 0.0

    def feed(self):
        alive = [m for m in self.members if m.is_alive()]
        total_needed = len(alive) * assumptions.FOOD_REQUIRED_PER_MEMBER_PER_DAY

        if assumptions.FEED_ALL_OR_NONE and self.food < total_needed:
            return  # not enough food to feed everyone

        for m in alive:
            m.consume(food=assumptions.FOOD_REQUIRED_PER_MEMBER_PER_DAY)

        self.food -= total_needed

    def hydrate(self):
        alive = [m for m in self.members if m.is_alive()]
        total_needed = len(alive) * assumptions.WATER_REQUIRED_PER_MEMBER_PER_DAY

        if assumptions.FEED_ALL_OR_NONE and self.water < total_needed:
            return  # not enough water to hydrate everyone

        for m in alive:
            m.drink(assumptions.WATER_REQUIRED_PER_MEMBER_PER_DAY)

        self.water -= total_needed

    def maybe_reproduce(self):
        alive = [m for m in self.members if m.is_alive()]
        if len(alive) < assumptions.REPRODUCTION_MIN_MEMBERS:
            return

        if any(m.hunger >= assumptions.REPRODUCTION_HUNGER_LIMIT for m in alive):
            return  # at least one member is too hungry

        if random.random() < assumptions.REPRODUCTION_CHANCE:
            baby = Member(age=0)
            self.members.append(baby)
            #print(f"👶 {self.name} has a new baby: {baby.name}")

    def report(self):
        print(f"\n{self.name} - Members: {len(self.members)} | Food: {self.food:.2f} | Water: {self.water:.2f}")
        for m in self.members:
            print("  ", m)

    def __repr__(self):
        return f"<{self.name} | {len(self.members)} members | Food: {self.food:.1f} | Water: {self.water:.1f}>"
