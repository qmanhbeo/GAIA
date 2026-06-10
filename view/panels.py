from __future__ import annotations

from typing import Any


class Panels:
    def __init__(self, x: int, width: int, height: int):
        self.x = x
        self.width = width
        self.height = height

    def render(
        self,
        pygame: Any,
        surface: Any,
        fonts: dict[str, Any],
        snapshot: dict[str, Any],
        *,
        paused: bool,
        speed: float,
        selected_ref: tuple[str, str] | None,
    ) -> None:
        pygame.draw.rect(surface, (12, 18, 26), pygame.Rect(self.x, 0, self.width, self.height))
        pygame.draw.line(surface, (56, 75, 92), (self.x, 0), (self.x, self.height), 2)

        cursor_y = 22
        cursor_y = self._draw_text(surface, fonts["title"], "GAIA Spatial", self.x + 22, cursor_y, (238, 246, 247))
        cursor_y += 10

        metrics = snapshot.get("metrics", {})
        lines = [
            f"Tick: {snapshot.get('tick', 0)}",
            f"Clock: {snapshot.get('clock', {}).get('elapsed_time', '0 hours')}",
            f"State: {'paused' if paused else 'playing'}",
            f"Speed: {speed:.1f} ticks/sec",
            f"Population: {snapshot.get('population', metrics.get('population', 0))}",
            f"Food node stock: {snapshot.get('food_node_stock', metrics.get('food_node_stock', metrics.get('food_stock', 0.0))):.2f}",
            f"Home stored food: {snapshot.get('total_home_food', metrics.get('total_home_food', 0.0)):.2f}",
            f"Avg hunger: {snapshot.get('avg_hunger', metrics.get('avg_hunger', 0.0)):.3f}",
            f"Water stock: {snapshot.get('water_stock', metrics.get('water_stock', 0.0)):.2f}",
            f"Avg thirst: {snapshot.get('avg_thirst', metrics.get('avg_thirst', 0.0)):.3f}",
            f"Avg fatigue: {metrics.get('avg_fatigue', 0.0):.3f}",
            f"Fatigued: {metrics.get('fatigued_count', 0)}",
            f"Moving: {metrics.get('moving_agents', 0)}",
            f"Blocked/waiting: {metrics.get('blocked_agents', 0)}",
        ]
        for line in lines:
            cursor_y = self._draw_text(surface, fonts["body"], line, self.x + 22, cursor_y, (196, 213, 222))

        cursor_y += 14
        cursor_y = self._draw_text(surface, fonts["heading"], "Selected", self.x + 22, cursor_y, (238, 246, 247))
        for line in self._selected_lines(snapshot, selected_ref):
            cursor_y = self._draw_text(surface, fonts["body"], line, self.x + 22, cursor_y, (196, 213, 222))

        cursor_y += 14
        cursor_y = self._draw_text(surface, fonts["heading"], "Events", self.x + 22, cursor_y, (238, 246, 247))
        event_log = snapshot.get("event_log", [])
        if selected_ref is not None:
            key = "agent_id" if selected_ref[0] == "agent" else "node_id"
            filtered = [e for e in event_log if e.get(key) == selected_ref[1]]
        else:
            filtered = event_log
        if not filtered:
            cursor_y = self._draw_text(surface, fonts["small"], "None", self.x + 22, cursor_y, (151, 169, 180))
        else:
            for entry in filtered[-5:]:
                tick = entry.get("tick", "?")
                label = entry.get("agent_label", entry.get("agent_id", "?"))
                event = entry.get("event", "?")
                text = f"{tick} {label} {event}"
                amount = entry.get("amount")
                if amount is not None:
                    text += f" {amount:.2f}"
                cursor_y = self._draw_text(surface, fonts["small"], text, self.x + 22, cursor_y, (151, 169, 180))

        controls = ["Space pause/play", "N or Right step", "+/- speed", "Esc quit", "Click entity select"]
        cursor_y = max(cursor_y + 18, self.height - 132)
        cursor_y = self._draw_text(surface, fonts["heading"], "Controls", self.x + 22, cursor_y, (238, 246, 247))
        for line in controls:
            cursor_y = self._draw_text(surface, fonts["small"], line, self.x + 22, cursor_y, (151, 169, 180))

    def _selected_lines(self, snapshot: dict[str, Any], selected_ref: tuple[str, str] | None) -> list[str]:
        if selected_ref is None:
            return ["None"]

        collection = "agents" if selected_ref[0] == "agent" else "nodes"
        entity = next((item for item in snapshot.get(collection, []) if item.get("id") == selected_ref[1]), None)
        if entity is None:
            return ["Missing"]

        if selected_ref[0] == "agent":
            return [
                f"{entity.get('label', entity.get('id'))} ({entity.get('type', 'agent')})",
                f"State: {entity.get('state', 'unknown')}",
                f"Position: {entity.get('x')}, {entity.get('y')}",
                f"Hunger: {entity.get('hunger', 0.0):.3f}",
                f"Thirst: {entity.get('thirst', 0.0):.3f}",
                f"Health: {entity.get('health', 0.0):.3f}",
                f"Carried food: {entity.get('carried_food', 0.0):.3f}/{entity.get('carry_capacity', 0.0):.3f}",
                f"Target: {entity.get('target_kind') or 'none'}",
                f"Action: {entity.get('last_action', 'none')}",
            ]

        if entity.get("kind") == "home":
            return [
                f"{entity.get('label', entity.get('id'))} (home)",
                f"Position: {entity.get('x')}, {entity.get('y')}",
                f"Stored food: {entity.get('stored_food', 0.0):.3f}",
                f"Storage cap: {entity.get('stored_food_capacity', 0.0):.3f}",
            ]

        return [
            f"{entity.get('label', entity.get('id'))} ({entity.get('kind', 'node')})",
            f"Type: {entity.get('type', 'node')}",
            f"Position: {entity.get('x')}, {entity.get('y')}",
            f"Stock: {entity.get('stock', 0.0):.3f}",
            f"Capacity: {entity.get('capacity', 0.0):.3f}",
        ]

    def _draw_text(
        self,
        surface: Any,
        font: Any,
        text: str,
        x: int,
        y: int,
        color: tuple[int, int, int],
    ) -> int:
        rendered = font.render(text, True, color)
        surface.blit(rendered, (x, y))
        return y + rendered.get_height() + 7
