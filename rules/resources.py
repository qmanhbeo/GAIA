from __future__ import annotations

from typing import Any


class ResourceRule:
    def apply(self, engine: Any) -> None:
        for node in engine.nodes:
            node.stock = min(node.capacity, node.stock + node.replenish_per_tick)
