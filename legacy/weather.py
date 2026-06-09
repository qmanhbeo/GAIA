import math
import random

from . import assumptions

class Weather:
    """
    Weather with all random knobs defined in assumptions.py.
    """
    def __init__(self, day):
        self.day = day

        # Draw parameters from assumptions
        amp_min, amp_max = assumptions.RAIN_AMP_FACTOR_RANGE
        phase_min, phase_max = assumptions.RAIN_PHASE_SHIFT_RANGE
        rain_noise_min, rain_noise_max = assumptions.RAIN_NOISE_RANGE
        drought_noise_min, drought_noise_max = assumptions.DROUGHT_NOISE_RANGE

        # Randomize amplitude multiplier and phase shift
        amp_factor  = random.uniform(amp_min, amp_max)
        phase_shift = random.uniform(phase_min, phase_max)

        # Compute phase (0→2π) including shift
        phase = (day / assumptions.RAIN_CYCLE_DAYS + phase_shift) * 2 * math.pi

        # Sine-wave base plus small noise
        raw_rain = math.sin(phase)
        rain_noise = random.uniform(rain_noise_min, rain_noise_max)
        self.rainfall = (
            assumptions.BASE_RAINFALL
            + amp_factor * assumptions.RAIN_AMPLITUDE * raw_rain
            + rain_noise
        )
        self.rainfall = max(0.0, min(1.0, self.rainfall))  # clamp 0–1

        # Drought opposite in phase, with independent noise
        drought_raw = math.sin(phase + math.pi)
        drought_noise = random.uniform(drought_noise_min, drought_noise_max)
        self.drought_factor = (
            assumptions.BASE_DROUGHT
            + amp_factor * assumptions.DROUGHT_AMPLITUDE * drought_raw
            + drought_noise
        )
        self.drought_factor = max(0.0, self.drought_factor)

        # Storm chance unchanged
        self.storm = (random.random() < assumptions.STORM_PROBABILITY)

    def __repr__(self):
        return (
            f"<Weather Day {self.day}: "
            f"Rainfall={self.rainfall:.2f}, "
            f"Drought={self.drought_factor:.2f}, "
            f"Storm={self.storm}>"
        )
