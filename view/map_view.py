from __future__ import annotations

from typing import Any


def _hex_to_rgb(value: str, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
    if not isinstance(value, str) or not value.startswith("#") or len(value) != 7:
        return fallback
    try:
        return tuple(int(value[index : index + 2], 16) for index in (1, 3, 5))
    except ValueError:
        return fallback


class MapView:
    def __init__(self, tile_size: int):
        self.tile_size = tile_size

    def render(self, pygame: Any, surface: Any, snapshot: dict[str, Any], selected_ref: tuple[str, str] | None) -> None:
        tile_size = self.tile_size
        for tile in snapshot.get("tiles") or snapshot.get("grid", {}).get("tiles", []):
            x = int(tile["x"]) * tile_size
            y = int(tile["y"]) * tile_size
            color = _hex_to_rgb(tile.get("color", ""), (18, 31, 44))
            rect = pygame.Rect(x, y, tile_size, tile_size)
            pygame.draw.rect(surface, color, rect)
            pygame.draw.rect(surface, (31, 48, 63), rect, 1)

            if not tile.get("passable", True):
                pygame.draw.line(surface, (84, 105, 126), rect.topleft, rect.bottomright, 2)
                pygame.draw.line(surface, (84, 105, 126), rect.bottomleft, rect.topright, 2)

        for node in snapshot.get("nodes", []):
            center = self._center(node)
            color = _hex_to_rgb(node.get("color", ""), (240, 210, 120))
            radius = max(5, tile_size // 4)
            pygame.draw.circle(surface, color, center, radius)
            pygame.draw.circle(surface, (10, 16, 22), center, radius, 2)
            if selected_ref == ("node", node.get("id")):
                pygame.draw.circle(surface, (255, 255, 255), center, radius + 4, 2)

        for agent in snapshot.get("agents", []):
            if agent.get("health", 0) <= 0:
                color = (95, 95, 95)
            elif agent.get("state") in {"eating", "drinking"}:
                color = (255, 238, 122)
            elif agent.get("state") in {"blocked", "waiting"}:
                color = (255, 119, 91)
            else:
                color = (232, 245, 255)
            center = self._center(agent)
            radius = max(4, tile_size // 5)
            pygame.draw.circle(surface, color, center, radius)
            pygame.draw.circle(surface, (8, 12, 18), center, radius, 1)
            if selected_ref == ("agent", agent.get("id")):
                pygame.draw.circle(surface, (255, 255, 255), center, radius + 4, 2)

    def pick_entity(self, snapshot: dict[str, Any], pixel_position: tuple[int, int]) -> tuple[str, str] | None:
        tile_x = pixel_position[0] // self.tile_size
        tile_y = pixel_position[1] // self.tile_size
        for agent in snapshot.get("agents", []):
            if int(agent.get("x", -1)) == tile_x and int(agent.get("y", -1)) == tile_y:
                return ("agent", str(agent["id"]))
        for node in snapshot.get("nodes", []):
            if int(node.get("x", -1)) == tile_x and int(node.get("y", -1)) == tile_y:
                return ("node", str(node["id"]))
        return None

    def _center(self, entity: dict[str, Any]) -> tuple[int, int]:
        return (
            int(entity.get("x", 0)) * self.tile_size + self.tile_size // 2,
            int(entity.get("y", 0)) * self.tile_size + self.tile_size // 2,
        )
