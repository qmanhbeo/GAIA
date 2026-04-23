# Cozy Night Village Vibe

## Core Direction

Top-down 2D pixel village at night. The target feeling is cozy, quiet, slightly magical, and a little scholarly rather than heroic or grim.

Think:
- warm amber light inside a mostly dark world
- a central campfire acting as the emotional anchor
- small village buildings that feel lived-in and useful
- soft exploration, short walking distances, and friendly NPC presence

## Visual Rules

- Use a dark base canvas: `#0a0604`
- Keep the world low-saturation overall, then spend brightness on fire, windows, lanterns, and prompts
- Stay in 16x16 pixel language for tiles and simple readable sprite silhouettes
- Prefer brown, umber, soot, ember, and parchment colors over neon or high-contrast fantasy palettes
- Buildings should read clearly from shape and roof color before detail

## Anchor Palette

- Night background: `#0a0604`
- Dark soil: `#19110c`
- Path brown: `#4b331d`
- Warm roof/wall range: `#5d462d`, `#76471f`, `#6f3521`, `#8a4f24`
- Fire / window glow: `#f4c46d`, `#ffd27b`

## Spatial Layout

The village is a compact four-corners layout around a single center point:

```text
  [Library NW]         [Workshop NE]
      (8,8)               (26,8)
        \                   /
         \                 /
          \               /
           [campfire] (20,20)
          /               \
         /                 \
        /                   \
   [Tavern SW]        [Post Office SE]
     (8,26)               (26,26)
```

Reference world size:
- `40 x 40` tiles
- `16 px` per tile
- `640 x 640 px` total map

## Character Tone

- Avery: warm guide near the campfire, first point of trust
- Alex: thoughtful library-side NPC
- Adam: builder / prototype energy near the workshop

Dialogue should be short, calm, and slightly intimate. Avoid exposition-heavy writing.

## Audio Direction

The intended sound layer is:
- soft medieval or tavern-adjacent background music
- light footstep Foley
- subtle door-enter cue
- tiny dialogue blips

Audio should support the firelit calm, not push the scene into combat or epic-adventure territory.
