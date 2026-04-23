Original prompt: ok let's just stick to PixiJS then. I just want a 2D renderer. Yes, the frontend's role is just to draw. So, based on the assumption that seeing the 2d grid first is more beneficial for later tweaking things, what's next to do? please do

- Started the first visible 2D slice as a separate spatial prototype instead of forcing the legacy v0.2 allocator into a fake map.
- Decision: keep Python authoritative and make the frontend replay snapshots only.
- Added `spatial_v1_prototype` mode in Python with per-tick snapshots, node coordinates, simple need-driven movement, and deterministic artifact export.
- Added `viewer/` as a PixiJS replay client with play/pause/step/reset, timeline scrubbing, selected-agent stats, and local artifact loading.
- Added `spatial_live_service.py` so the viewer can connect to a live Python stepping session over HTTP.
- Added `run_spatial_world.sh` so the live service and PixiJS viewer can be launched together from the repo root with one command.
- Generated `viewer/public/demo-spatial.json` as the default replay artifact.
- Verified the Python export via unit tests and verified the PixiJS viewer visually with a browser screenshot plus `render_game_to_text`.
- Verified replay controls and direct agent selection in the PixiJS viewer through browser automation.
- Verified live stepping end to end through the Python service and the PixiJS viewer.
- Confirmed and fixed a play-mode animation bug in `viewer/src/main.js`: the viewer had been interpolating from `frameIndex - 1` to `frameIndex` while a free-running accumulator continued through async live updates, which caused visible snapping during `Play`.
- Reworked playback to use explicit transitions (`fromFrame -> toFrame`) for both replay and live mode, so a new tween starts only when a new frame exists instead of being inferred from `frameIndex`.
- Verified the fix with `npm run build`, Python unit tests, live browser sampling through Playwright, and a screenshot sanity check of the live viewer.
- TODO: decide whether the next step is better spatial legibility, richer movement rules, or viewer-driven interventions/config changes.
