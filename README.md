# GAIA

GAIA is now a single Python-native spatial simulation app.

The active path is:

```bash
python main.py
```

That command opens a Pygame window, runs the current spatial GAIA world, and renders the engine snapshot as a tile map plus numeric panels. The engine owns the simulation state; the viewer only renders snapshots and sends simple control input.

## Setup

GAIA requires Python 3.10+.

```bash
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

Useful parameters:

```bash
python main.py --days 300
python main.py --households 2
python main.py --members 10
python main.py --grid-width 24
python main.py --grid-height 16
python main.py --seed 42
```

Headless smoke run:

```bash
python main.py --headless --days 10
```

Export a spatial artifact:

```bash
python main.py --artifact --days 120 --households 1 --members 6 --grid-width 18 --grid-height 12 --out viewer/public/demo-spatial.json
```

## Controls

- `Space` = pause/play
- `N` or `Right Arrow` = single step
- `+` / `-` = speed up/down
- `Click` = select an agent or node
- `Esc` = quit

## Active Structure

- `main.py` is the public entry point and control tower.
- `spatial_simulation.py` contains the active spatial engine.
- `gaia_config.py` contains active spatial runtime config.
- `simulation_artifact.py` contains the shared artifact wrapper.
- `spatial_live_service.py` remains for the existing PixiJS live viewer.
- `view/` contains the lightweight Pygame renderer.

## Snapshot Contract

The Pygame map and stats panel read the same engine snapshot. Current fields include:

- `tick`
- `clock`
- `population`
- `food_stock`
- `food_node_stock`
- `total_home_food`
- `home_storage_capacity`
- `water_stock`
- `avg_hunger`
- `avg_thirst`
- `agents`
- `nodes`
- `tiles`
- `events`
- `grid`
- `metrics`
- `selected_agent`

One tick currently equals one hour.

Food nodes expose `stock`; home nodes expose `stored_food` and `stored_food_capacity`; agents expose `home_id`, `carried_food`, and `carry_capacity`.

## Archived Legacy Model

The old abstract, non-spatial model has been archived in `legacy/`. It is no longer the active development path and is not used by `python main.py`.

Archived files:

- `legacy/simulation.py`
- `legacy/household.py`
- `legacy/member.py`
- `legacy/farm.py`
- `legacy/water.py`
- `legacy/weather.py`
- `legacy/simLogger.py`
- `legacy/assumptions.py`

The current development focus is food stock, hunger, movement, and survival in the spatial world. Streamlit and the PixiJS viewer may remain as secondary tools, but they are not the main path.
