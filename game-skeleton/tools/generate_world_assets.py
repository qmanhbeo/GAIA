#!/usr/bin/env python3
"""Generate portable pixel art assets for the game-skeleton bundle."""

from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHARACTER_DIR = ROOT / "assets" / "characters"
TILESET_DIR = ROOT / "assets" / "tilesets"
MAP_DIR = ROOT / "assets" / "maps"

RGBA = tuple[int, int, int, int]

TRANSPARENT: RGBA = (0, 0, 0, 0)
OUTLINE: RGBA = (28, 15, 10, 255)
SHADOW: RGBA = (0, 0, 0, 88)
SKIN: RGBA = (245, 208, 139, 255)
SKIN_NPC: RGBA = (241, 201, 152, 255)
EYE: RGBA = (42, 22, 14, 255)
AMBER: RGBA = (255, 210, 123, 255)


def write_png(path: Path, width: int, height: int, pixels: list[list[RGBA]]) -> None:
    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + chunk_type
            + data
            + struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
        )

    raw = b"".join(b"\x00" + b"".join(bytes(pixel) for pixel in row) for row in pixels)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def blank(width: int, height: int) -> list[list[RGBA]]:
    return [[TRANSPARENT for _ in range(width)] for _ in range(height)]


def clamp(value: int) -> int:
    return max(0, min(255, value))


def shift(color: RGBA, amount: int) -> RGBA:
    return (
        clamp(color[0] + amount),
        clamp(color[1] + amount),
        clamp(color[2] + amount),
        color[3],
    )


def rect(pixels: list[list[RGBA]], x: int, y: int, width: int, height: int, color: RGBA) -> None:
    for row in range(max(0, y), min(len(pixels), y + height)):
        for col in range(max(0, x), min(len(pixels[row]), x + width)):
            pixels[row][col] = color


def ellipse(pixels: list[list[RGBA]], cx: float, cy: float, rx: float, ry: float, color: RGBA) -> None:
    for row in range(len(pixels)):
        for col in range(len(pixels[row])):
            if ((col + 0.5 - cx) / rx) ** 2 + ((row + 0.5 - cy) / ry) ** 2 <= 1:
                pixels[row][col] = color


def triangle(
    pixels: list[list[RGBA]],
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
    color: RGBA,
) -> None:
    def edge(p: tuple[float, float], q: tuple[float, float], r: tuple[float, float]) -> float:
        return (r[0] - p[0]) * (q[1] - p[1]) - (r[1] - p[1]) * (q[0] - p[0])

    min_x = int(max(0, min(a[0], b[0], c[0])))
    max_x = int(min(len(pixels[0]) - 1, max(a[0], b[0], c[0])))
    min_y = int(max(0, min(a[1], b[1], c[1])))
    max_y = int(min(len(pixels) - 1, max(a[1], b[1], c[1])))

    for row in range(min_y, max_y + 1):
      for col in range(min_x, max_x + 1):
        point = (col + 0.5, row + 0.5)
        w0 = edge(b, c, point)
        w1 = edge(c, a, point)
        w2 = edge(a, b, point)
        if (w0 >= 0 and w1 >= 0 and w2 >= 0) or (w0 <= 0 and w1 <= 0 and w2 <= 0):
            pixels[row][col] = color


def scatter(pixels: list[list[RGBA]], color: RGBA, seed: int, period: int, opacity: int = 255) -> None:
    for row in range(len(pixels)):
        for col in range(len(pixels[row])):
            if (col * 17 + row * 29 + seed * 11) % period == 0:
                pixels[row][col] = (color[0], color[1], color[2], opacity)


def ground_tile(base: RGBA, seed: int) -> list[list[RGBA]]:
    pixels = blank(16, 16)
    rect(pixels, 0, 0, 16, 16, base)
    scatter(pixels, shift(base, 12), seed, 19)
    scatter(pixels, shift(base, -10), seed + 4, 23)
    rect(pixels, 0, 15, 16, 1, shift(base, -14))
    rect(pixels, 15, 0, 1, 16, shift(base, -10))
    return pixels


def path_tile(base: RGBA, seed: int, edge: bool = False) -> list[list[RGBA]]:
    pixels = blank(16, 16)
    rect(pixels, 0, 0, 16, 16, base)
    if edge:
        rect(pixels, 0, 0, 2, 16, (29, 21, 14, 255))
        rect(pixels, 14, 0, 2, 16, (29, 21, 14, 255))
    scatter(pixels, shift(base, 24), seed, 17)
    scatter(pixels, shift(base, -18), seed + 2, 13)
    rect(pixels, 0, 15, 16, 1, shift(base, -16))
    return pixels


def roof_tile(kind: str) -> list[list[RGBA]]:
    pixels = blank(16, 16)
    dark: RGBA = (42, 21, 13, 255)
    mid: RGBA = (96, 48, 24, 255)
    light: RGBA = (163, 91, 43, 255)
    rect(pixels, 0, 3, 16, 13, dark)
    rect(pixels, 0, 5, 16, 9, mid)
    rect(pixels, 0, 9, 16, 2, (69, 33, 19, 255))
    if kind == "left":
        triangle(pixels, (15, 3), (0, 15), (15, 15), dark)
        rect(pixels, 12, 5, 4, 9, light)
    elif kind == "right":
        triangle(pixels, (0, 3), (0, 15), (15, 15), dark)
        rect(pixels, 0, 5, 4, 9, light)
    else:
        rect(pixels, 0, 4, 16, 2, light)
        rect(pixels, 0, 11, 16, 1, (34, 16, 10, 255))
    rect(pixels, 0, 15, 16, 1, (23, 11, 8, 255))
    return pixels


def wall_tile(base: RGBA) -> list[list[RGBA]]:
    pixels = blank(16, 16)
    rect(pixels, 0, 0, 16, 16, base)
    rect(pixels, 0, 0, 16, 1, shift(base, 18))
    rect(pixels, 0, 7, 16, 1, shift(base, -18))
    rect(pixels, 0, 15, 16, 1, shift(base, -26))
    for col in (4, 11):
        rect(pixels, col, 1, 1, 14, shift(base, -14))
    scatter(pixels, shift(base, 10), base[0], 31)
    return pixels


def window_tile() -> list[list[RGBA]]:
    pixels = blank(16, 16)
    rect(pixels, 3, 4, 10, 9, (35, 18, 11, 255))
    rect(pixels, 4, 5, 8, 7, (244, 196, 109, 230))
    rect(pixels, 4, 8, 8, 1, (143, 83, 41, 255))
    rect(pixels, 7, 5, 1, 7, (143, 83, 41, 255))
    rect(pixels, 5, 6, 2, 2, (255, 224, 150, 255))
    return pixels


def door_tile() -> list[list[RGBA]]:
    pixels = blank(16, 16)
    rect(pixels, 3, 1, 10, 15, (33, 17, 11, 255))
    rect(pixels, 4, 2, 8, 14, (84, 43, 24, 255))
    rect(pixels, 5, 3, 6, 2, (119, 65, 33, 255))
    rect(pixels, 10, 8, 2, 2, (255, 197, 94, 255))
    return pixels


def sign_tile() -> list[list[RGBA]]:
    pixels = blank(16, 16)
    rect(pixels, 2, 5, 12, 6, (48, 26, 15, 255))
    rect(pixels, 3, 6, 10, 4, (187, 126, 60, 255))
    rect(pixels, 5, 8, 6, 1, (255, 223, 151, 255))
    return pixels


def lantern_tile() -> list[list[RGBA]]:
    pixels = blank(16, 16)
    rect(pixels, 7, 2, 2, 4, (37, 20, 13, 255))
    rect(pixels, 5, 6, 6, 7, (37, 20, 13, 255))
    rect(pixels, 6, 7, 4, 5, (255, 203, 103, 235))
    rect(pixels, 4, 5, 8, 8, (255, 174, 66, 55))
    return pixels


def compose_tileset(tiles: list[list[list[RGBA]]], columns: int = 4) -> list[list[RGBA]]:
    rows = (len(tiles) + columns - 1) // columns
    pixels = blank(columns * 16, rows * 16)
    for index, tile_pixels in enumerate(tiles):
        tile_x = (index % columns) * 16
        tile_y = (index // columns) * 16
        for row in range(16):
            for col in range(16):
                pixels[tile_y + row][tile_x + col] = tile_pixels[row][col]
    return pixels


def generate_tileset() -> None:
    tiles = [
        ground_tile((25, 17, 12, 255), 1),
        ground_tile((30, 21, 14, 255), 4),
        ground_tile((23, 20, 13, 255), 9),
        path_tile((72, 47, 27, 255), 2),
        path_tile((88, 59, 32, 255), 5),
        path_tile((65, 42, 25, 255), 7, edge=True),
        roof_tile("left"),
        roof_tile("middle"),
        roof_tile("right"),
        wall_tile((83, 64, 42, 255)),
        wall_tile((112, 67, 31, 255)),
        wall_tile((105, 50, 32, 255)),
        window_tile(),
        door_tile(),
        sign_tile(),
        lantern_tile(),
    ]
    write_png(TILESET_DIR / "tiny-town.png", 64, 64, compose_tileset(tiles))


def generate_world_map() -> None:
    width = 40
    height = 40
    ground = [[1 + ((col * 7 + row * 11) % 3 == 0) + ((col * 5 + row * 13) % 11 == 0) for col in range(width)] for row in range(height)]
    path = [[0 for _ in range(width)] for _ in range(height)]
    buildings = [[0 for _ in range(width)] for _ in range(height)]
    decor = [[0 for _ in range(width)] for _ in range(height)]

    def paint_path(left: int, top: int, right: int, bottom: int) -> None:
        for row in range(max(0, top), min(height, bottom + 1)):
            for col in range(max(0, left), min(width, right + 1)):
                path[row][col] = 4 + ((col + row) % 2)

    paint_path(18, 6, 21, 34)
    paint_path(6, 18, 34, 21)
    paint_path(7, 9, 18, 10)
    paint_path(21, 9, 32, 10)
    paint_path(7, 30, 18, 31)
    paint_path(21, 30, 32, 31)

    def stamp_building(col: int, row: int, wall_gid: int) -> None:
        roof_gids = [7, 8, 8, 8, 8, 9]
        for offset, gid in enumerate(roof_gids):
            buildings[row][col + offset] = gid
        for tile_row in range(row + 1, row + 5):
            for tile_col in range(col, col + 6):
                buildings[tile_row][tile_col] = wall_gid
        decor[row + 2][col + 1] = 13
        decor[row + 2][col + 4] = 13
        decor[row + 3][col + 2] = 15
        decor[row + 3][col + 4] = 16
        decor[row + 4][col + 2] = 14

    stamp_building(5, 4, 10)
    stamp_building(29, 4, 11)
    stamp_building(5, 28, 12)
    stamp_building(29, 28, 10)

    layers = [
        ("ground", ground),
        ("path", path),
        ("buildings", buildings),
        ("decor", decor),
    ]

    tiled_map = {
        "compressionlevel": -1,
        "height": height,
        "infinite": False,
        "layers": [
            {
                "data": [tile for map_row in data for tile in map_row],
                "height": height,
                "id": index + 1,
                "name": name,
                "opacity": 1,
                "type": "tilelayer",
                "visible": True,
                "width": width,
                "x": 0,
                "y": 0,
            }
            for index, (name, data) in enumerate(layers)
        ],
        "nextlayerid": len(layers) + 1,
        "nextobjectid": 1,
        "orientation": "orthogonal",
        "renderorder": "right-down",
        "tiledversion": "1.11.2",
        "tileheight": 16,
        "tilesets": [
            {
                "columns": 4,
                "firstgid": 1,
                "image": "../tilesets/tiny-town.png",
                "imageheight": 64,
                "imagewidth": 64,
                "margin": 0,
                "name": "tiny-town",
                "spacing": 0,
                "tilecount": 16,
                "tileheight": 16,
                "tilewidth": 16,
            },
        ],
        "tilewidth": 16,
        "type": "map",
        "version": "1.10",
        "width": width,
    }

    MAP_DIR.mkdir(parents=True, exist_ok=True)
    (MAP_DIR / "world.json").write_text(json.dumps(tiled_map, indent=2) + "\n")


def character(
    cloak: RGBA,
    hair: RGBA,
    accent: RGBA,
    skin: RGBA = SKIN_NPC,
    scarf: RGBA | None = None,
) -> list[list[RGBA]]:
    pixels = blank(24, 28)

    ellipse(pixels, 12, 25, 8.5, 2.5, SHADOW)
    rect(pixels, 6, 9, 12, 15, OUTLINE)
    rect(pixels, 5, 12, 14, 9, OUTLINE)
    rect(pixels, 6, 10, 12, 13, cloak)
    rect(pixels, 7, 11, 10, 6, tuple(max(0, channel - 18) if index < 3 else channel for index, channel in enumerate(cloak)))
    rect(pixels, 7, 18, 10, 5, tuple(max(0, channel - 34) if index < 3 else channel for index, channel in enumerate(cloak)))

    rect(pixels, 7, 4, 10, 10, OUTLINE)
    rect(pixels, 8, 5, 8, 8, skin)
    rect(pixels, 6, 3, 12, 4, hair)
    rect(pixels, 6, 6, 3, 4, hair)
    rect(pixels, 15, 6, 3, 4, hair)
    rect(pixels, 9, 8, 2, 2, EYE)
    rect(pixels, 14, 8, 2, 2, EYE)
    rect(pixels, 11, 11, 3, 1, (119, 63, 36, 255))

    rect(pixels, 7, 14, 10, 2, scarf or accent)
    rect(pixels, 10, 20, 4, 3, accent)
    rect(pixels, 8, 24, 3, 2, OUTLINE)
    rect(pixels, 14, 24, 3, 2, OUTLINE)

    return pixels


def campfire() -> list[list[RGBA]]:
    pixels = blank(32, 32)
    log_dark: RGBA = (42, 23, 16, 255)
    log_mid: RGBA = (125, 74, 36, 255)
    stone: RGBA = (58, 42, 34, 255)

    rect(pixels, 7, 20, 18, 3, log_dark)
    rect(pixels, 8, 24, 18, 3, log_dark)
    rect(pixels, 7, 19, 10, 4, log_mid)
    rect(pixels, 16, 23, 11, 4, log_mid)
    ellipse(pixels, 5, 23, 2.5, 2.5, stone)
    ellipse(pixels, 9, 27, 2.5, 2.5, stone)
    ellipse(pixels, 23, 27, 2.5, 2.5, stone)
    ellipse(pixels, 27, 23, 2.5, 2.5, stone)

    triangle(pixels, (16, 3), (8, 22), (24, 22), (255, 210, 123, 255))
    triangle(pixels, (16, 7), (10, 23), (22, 23), (255, 122, 36, 255))
    triangle(pixels, (16, 11), (13, 22), (19, 22), (255, 241, 183, 255))
    rect(pixels, 15, 24, 3, 4, (255, 210, 123, 255))

    return pixels


def main() -> None:
    sprites = {
        "player.png": character(
            cloak=(138, 79, 36, 255),
            hair=(58, 31, 19, 255),
            accent=AMBER,
            skin=SKIN,
            scarf=(255, 196, 88, 255),
        ),
        "npc-alex.png": character(
            cloak=(94, 137, 194, 255),
            hair=(36, 19, 12, 255),
            accent=(255, 210, 123, 255),
        ),
        "npc-adam.png": character(
            cloak=(86, 150, 77, 255),
            hair=(68, 48, 29, 255),
            accent=(255, 210, 123, 255),
        ),
        "npc-avery.png": character(
            cloak=(184, 132, 47, 255),
            hair=(32, 26, 36, 255),
            accent=(255, 235, 160, 255),
        ),
        "campfire.png": campfire(),
    }

    for filename, pixels in sprites.items():
        write_png(CHARACTER_DIR / filename, len(pixels[0]), len(pixels), pixels)

    generate_tileset()
    generate_world_map()


if __name__ == "__main__":
    main()
