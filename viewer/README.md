# GAIA PixiJS Viewer

This is the first visible 2D spatial viewer for GAIA.

It is intentionally narrow:

- it **does not** own the simulation rules
- it **does** replay spatial snapshots exported by Python
- it **can** connect to a live Python stepping service
- it exists to make movement, need pressure, and agent state legible before deeper economics are implemented

## Run It

### One Command From The Repo Root

If you just want the live spatial world without juggling two terminals, run:

```bash
./run_spatial_world.sh
```

You can change the defaults with environment variables:

```bash
GAIA_MEMBERS=10 GAIA_GRID_WIDTH=24 GAIA_GRID_HEIGHT=16 ./run_spatial_world.sh
```

This starts both:

- the Python live service on `http://127.0.0.1:8765`
- the PixiJS viewer on `http://127.0.0.1:4173`

Press `Ctrl-C` once to stop both.

### Replay Mode

From the repo root, export a replay artifact:

```bash
python main.py --mode spatial_v1_prototype --days 120 --households 1 --members 6 --grid-width 18 --grid-height 12 --artifact --out viewer/public/demo-spatial.json
```

Then start the viewer:

```bash
cd viewer
npm install
npm run dev
```

Open the local Vite URL, usually `http://127.0.0.1:4173/`.

### Live Mode

Start the Python live service from the repo root:

```bash
python spatial_live_service.py --port 8765 --days 240 --households 1 --members 6 --grid-width 18 --grid-height 12
```

Then start the viewer:

```bash
cd viewer
npm install
npm run dev
```

The viewer will try to connect to `http://127.0.0.1:8765` automatically. You can also force a different live URL with a query string:

```text
http://127.0.0.1:4173/?live=http://127.0.0.1:9000
```

## Current Features

- fixed grid replay
- rendered terrain tiles with blocked rock barriers and slower terrain patches
- weighted pathfinding over the tile grid
- occupancy-aware movement on constrained tiles
- explicit node arrival before food or water can be consumed
- live stepping from Python
- home / food / water nodes
- per-tick agent movement
- play / pause / step / reset
- timeline scrubbing
- selected-agent stats
- local artifact upload

## Contract

The viewer expects a structured artifact with:

- `metadata`
- `time_series`
- `final_state`
- `snapshots`

Each snapshot should include:

- `tick`
- `grid`
- `nodes`
- `agents`
- `metrics`
- `selected_agent`

The frontend only draws this state. Python remains authoritative.
