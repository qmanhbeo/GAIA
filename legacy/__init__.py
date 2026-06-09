"""Archived abstract GAIA model.

The active application path is the spatial engine in the repository root.
This package keeps the previous non-spatial model importable for reference.
"""

from .simulation import LEGACY_MODE, LegacySimulationConfig, SimulationEngine

__all__ = ["LEGACY_MODE", "LegacySimulationConfig", "SimulationEngine"]
