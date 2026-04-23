# Game Skeleton

Portable reference bundle for the cozy night-village game vibe used by this repo's `/world` route.

This folder is intentionally not imported or used anywhere in the portfolio app. It exists so you can lift it into another game project as a mood, asset, and layout reference without dragging over the website code.

## Contents

- `assets/characters/` - generated player, NPC, and campfire sprites
- `assets/tilesets/` - generated `tiny-town.png` 16x16 tileset
- `assets/maps/` - generated `world.json` tilemap
- `tools/generate_world_assets.py` - portable regeneration script for the copied assets
- `docs/VIBE.md` - short art-direction and mood brief
- `docs/ASSET_SOURCES.md` - provenance and regeneration notes
- `reference/world-layout.json` - portable building and NPC placement reference

## How To Use It

1. Copy `game-skeleton/` into the other project.
2. Keep `assets/` as-is or move the files into that project's asset structure.
3. Use `reference/world-layout.json` and `docs/VIBE.md` as the brief for collaborators.
4. Regenerate the bundled art with `python3 tools/generate_world_assets.py` if you want fresh copies.

## What Is Deliberately Left Out

- No Next.js, React, or portfolio-specific route code
- No section-panel wiring to projects/publications/blog/letter
- No audio files yet, only the intended audio direction in the docs
