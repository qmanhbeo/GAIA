# GAIA PixiJS Viewer

This is the first visible 2D spatial viewer for GAIA.

It is intentionally narrow:

- it **does not** run the simulation
- it **does** replay spatial snapshots exported by Python
- it exists to make movement, need pressure, and agent state legible before deeper economics are implemented

## Run It

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

## Current Features

- fixed grid replay
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
