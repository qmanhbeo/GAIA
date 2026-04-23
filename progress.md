Original prompt: ok let's just stick to PixiJS then. I just want a 2D renderer. Yes, the frontend's role is just to draw. So, based on the assumption that seeing the 2d grid first is more beneficial for later tweaking things, what's next to do? please do

- Started the first visible 2D slice as a separate spatial prototype instead of forcing the legacy v0.2 allocator into a fake map.
- Decision: keep Python authoritative and make the frontend replay snapshots only.
- Added `spatial_v1_prototype` mode in Python with per-tick snapshots, node coordinates, simple need-driven movement, and deterministic artifact export.
- Added `viewer/` as a PixiJS replay client with play/pause/step/reset, timeline scrubbing, selected-agent stats, and local artifact loading.
- Generated `viewer/public/demo-spatial.json` as the default replay artifact.
- Verified the Python export via unit tests and verified the PixiJS viewer visually with a browser screenshot plus `render_game_to_text`.
- Verified replay controls and direct agent selection in the PixiJS viewer through browser automation.
- TODO: decide whether the next step is live Python-to-browser stepping, richer spatial rules, or replacing replay-only mode with a live state feed.
