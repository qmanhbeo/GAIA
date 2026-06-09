from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class SimulationArtifact:
    metadata: dict[str, Any]
    time_series: dict[str, list[Any]]
    final_state: dict[str, Any]
    snapshots: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata,
            "time_series": self.time_series,
            "final_state": self.final_state,
            "snapshots": self.snapshots,
        }

    def to_dataframe(self) -> pd.DataFrame:
        df = pd.DataFrame(self.time_series)
        if "day" in df.columns:
            df = df.sort_values("day").set_index("day")
        elif "tick" in df.columns:
            df = df.sort_values("tick").set_index("tick")
        return df
