# assumptions.py

# === Labor Eligibility ===
MIN_WORKING_AGE = 15
MAX_WORKING_AGE = 60

# === Aging & Mortality ===
MAX_AGE = 85
DAILY_AGING = 1  # member ages 1 unit per day

# === Hunger & Health ===
HUNGER_INCREASE_PER_LABOR = 0.1
HUNGER_THRESHOLD_FOR_DAMAGE = 1.0
HEALTH_LOSS_FROM_STARVATION = 0.1

# === Feeding ===
FOOD_REQUIRED_PER_MEMBER_PER_DAY = 1.0
FEED_ALL_OR_NONE = True  # if False, partial feeding logic can be implemented

# === Reproduction ===
REPRODUCTION_MIN_MEMBERS = 2
REPRODUCTION_HUNGER_LIMIT = 0.5
REPRODUCTION_CHANCE = 0.5  # 50% chance per eligible household per day

# === Farm Output ===
FARM_LABOR_NEEDED = 3.0  # labor needed to produce base output
FARM_BASE_OUTPUT = 10.0  # base units of food per day
FARM_SURPLUS_EFFICIENCY = 0.5  # conversion rate of surplus labor to extra food

# === Food Distribution ===
EQUAL_DISTRIBUTION = True  # food is split evenly across all households

# === Hydration ===
WATER_REQUIRED_PER_MEMBER_PER_DAY = 1.0
DAILY_HYDRATION_DECAY = 0.1
DEHYDRATION_THRESHOLD = 0.3
HEALTH_LOSS_FROM_DEHYDRATION = 0.1

# === Weather System ===
BASE_RAINFALL = 0.6            # baseline rainfall factor (0 to 1)
RAIN_AMPLITUDE = 0.4           # seasonal oscillation strength
RAIN_CYCLE_DAYS = 30           # wet–dry cycle in days

BASE_DROUGHT = 1.0             # normal crop productivity multiplier
DROUGHT_AMPLITUDE = 0.3        # how much drought fluctuates

STORM_PROBABILITY = 0.02       # 2% chance of destructive storm per day

# === Weather Randomization Parameters ===
# Multiplier on seasonal amplitude: pick uniformly between these
RAIN_AMP_FACTOR_RANGE     = (0.8, 1.2)
# Phase shift, in cycles (± fraction of a full sine wave)
RAIN_PHASE_SHIFT_RANGE    = (-0.25, 0.25)
# Day-to-day noise added to rainfall and drought
RAIN_NOISE_RANGE          = (-0.05, 0.05)
DROUGHT_NOISE_RANGE       = (-0.05, 0.05)
