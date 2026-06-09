from __future__ import annotations

from typing import Any

from gaia_config import DEFAULT_VIEWER_SPEED

from .map_view import MapView
from .panels import Panels


def run_pygame_app(engine: Any) -> None:
    try:
        import pygame
    except ModuleNotFoundError as exc:
        raise RuntimeError("Pygame is required for the default GAIA viewer. Run `pip install -r requirements.txt`.") from exc

    pygame.init()
    snapshot = engine.snapshot()
    grid = snapshot.get("grid", {})
    grid_width = int(grid.get("width", 24))
    grid_height = int(grid.get("height", 16))
    tile_size = max(18, min(36, 840 // max(1, grid_width), 720 // max(1, grid_height)))
    map_width = grid_width * tile_size
    map_height = grid_height * tile_size
    panel_width = 330
    window_size = (map_width + panel_width, max(map_height, 560))

    screen = pygame.display.set_mode(window_size)
    pygame.display.set_caption("GAIA Spatial World")
    clock = pygame.time.Clock()
    fonts = {
        "title": pygame.font.SysFont("dejavuserif", 28, bold=True),
        "heading": pygame.font.SysFont("dejavuserif", 18, bold=True),
        "body": pygame.font.SysFont("dejavuserif", 16),
        "small": pygame.font.SysFont("dejavuserif", 14),
    }
    map_view = MapView(tile_size=tile_size)
    panels = Panels(x=map_width, width=panel_width, height=window_size[1])

    paused = False
    speed = DEFAULT_VIEWER_SPEED
    accumulator = 0.0
    selected_ref: tuple[str, str] | None = None
    running = True

    while running:
        elapsed_seconds = clock.tick(60) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key in (pygame.K_RIGHT, pygame.K_n):
                    if engine.tick < engine.config.days:
                        snapshot = engine.step()
                elif event.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                    speed = min(24.0, speed + 1.0)
                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    speed = max(1.0, speed - 1.0)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if event.pos[0] < map_width and event.pos[1] < map_height:
                    selected_ref = map_view.pick_entity(snapshot, event.pos)

        if not paused and engine.tick < engine.config.days:
            accumulator += elapsed_seconds
            seconds_per_step = 1.0 / speed
            while accumulator >= seconds_per_step and engine.tick < engine.config.days:
                snapshot = engine.step()
                accumulator -= seconds_per_step
        elif engine.tick >= engine.config.days:
            paused = True
            accumulator = 0.0

        screen.fill((5, 9, 14))
        map_view.render(pygame, screen, snapshot, selected_ref)
        panels.render(
            pygame,
            screen,
            fonts,
            snapshot,
            paused=paused,
            speed=speed,
            selected_ref=selected_ref,
        )
        pygame.display.flip()

    pygame.quit()
