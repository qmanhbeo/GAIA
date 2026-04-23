# GAIA — Agent-Based Simulation of Resource Allocation

GAIA is an early-stage, bottom-up agent-based simulation exploring how households, labor, food, water, and environmental constraints interact over time under different resource allocation rules.

The project follows an incremental development approach, where architectural clarity precedes algorithmic complexity.

The project focuses on **building the environment first**: defining agents, assumptions, and system dynamics in a way that makes collective behavior observable, inspectable, and extensible.

This repository contains a working simulation engine and an interactive visualizer for running and analyzing experiments.

---

## What GAIA Is

GAIA models a simplified society composed of:

- **Individuals (Members)** who age, work, consume food and water, and experience health deterioration.
- **Households** that aggregate members, manage private food and water storage, and reproduce under health and resource constraints.
- **A Farm** that converts collective labor into food with diminishing returns and weather sensitivity.
- **A Water Source** that distributes water based on rainfall.
- **A Weather system** that introduces seasonal cycles, stochastic rainfall, and drought effects.
- **A World controller (SimulationEngine)** that wires all interactions together day by day.

The simulation runs in discrete time steps (“days”) and produces observable system-level dynamics such as population change, labor supply, food availability, and average health.

---

## Design Principles

GAIA is built around a few explicit principles:

- **Bottom-up modeling**: agents own their internal state and behavior; system outcomes emerge from interactions.
- **Separation of concerns**:  
  - Agents do not call each other directly.  
  - Environmental logic (weather, production, allocation) is handled at the world level.  
- **Explicit assumptions**: all economic, biological, and environmental parameters are centralized in `assumptions.py` to make policy and rule changes transparent.
- **Inspectability over optimization**: the goal is to understand system behavior, not to maximize a predefined objective.

---

## What Exists Today

Currently implemented:

- Agent classes for individuals and households
- Food production with labor constraints and diminishing returns
- Water distribution linked to rainfall
- Seasonal and stochastic weather dynamics
- Health, hunger, hydration, aging, death, and reproduction
- Equal food distribution as a baseline allocation rule
- Centralized simulation loop with clean logging
- Streamlit dashboard for interactive runs and time-series visualization

This is a **working simulation**, not a mockup.

---

## What This Project Does *Not* Claim (Yet)

GAIA does **not** currently include:

- Reinforcement learning agents
- Markets, prices, or money
- Strategic decision-making beyond local survival rules
- Calibration to real-world datasets
- Normative claims about “optimal” allocation

Those are intentional omissions at this stage.

---

## Why Build This First

The project treats GAIA as a **simulation environment**, not as an algorithm.

Before introducing learning agents or optimization, the hard problems must be addressed:

- What information exists in the world?
- What actions are possible?
- What trade-offs emerge between efficiency, fairness, stability, and sustainability?
- How do time scales (daily survival vs. long-term population change) interact?

GAIA is designed to make those questions concrete.

---

## Planned Extensions

The current architecture is designed to support future work, including:

- Alternative allocation mechanisms (beyond equal distribution)
- Centralized or decentralized planning agents
- Reinforcement learning applied to allocation and production decisions
- Multi-objective reward formulations (equality, efficiency, resilience)
- Integration with real household-level data
- Human or AI feedback as part of the reward signal

In this framing, **GAIA is the environment**. Learning systems are intended to be layered on top once the world dynamics are sufficiently well-defined.

---

## Stack Direction

GAIA is being built as a **Python-first simulation lab**, not as a traditional game-engine project.

The intended stack is:

- **Simulation core:** custom Python engine
- **Research console:** Streamlit
- **Future 2D world viewer:** PixiJS in the browser
- **RL interfaces later:** Gymnasium first, PettingZoo if the environment is later exposed as a true multi-agent API

What this means in practice:

- **Streamlit is the experiment console**, not the permanent game surface.
- Streamlit is a good fit for controls, charts, replay, snapshots, and debugging.
- Streamlit is **not** the ideal long-term renderer for a continuously updating spatial world with many moving agents.
- When the spatial model becomes real, the intended direction is to keep Streamlit for lab workflows and add a separate browser-based 2D renderer.

Non-default decisions:

- **Mesa** is a useful reference for agent-based modeling, but it is **not** the planned core architecture for GAIA.
- **Godot** is not the current target stack. It becomes relevant only if GAIA shifts from a research lab toward a full game product.

---

## Visualization Status

GAIA is currently **visualizable** and now has a **live 2D spatial prototype**, but it is still not a full game or a rich economic world.

What exists today:

- a working Python simulation engine
- a Streamlit dashboard for interactive runs
- post-run charts and metrics
- structured run artifacts with metadata, time series, final state, and snapshots
- a PixiJS viewer that can replay saved spatial artifacts
- a live Python spatial service that the PixiJS viewer can step in real time
- terrain tiles with movement cost, blocked rock barriers, and a visible road corridor
- weighted pathfinding over the grid instead of straight-line movement
- occupancy-aware movement so agents cannot freely overlap on constrained tiles
- explicit node arrival and resource depletion before food or water are consumed

What does **not** exist yet:

- queues, congestion, and institutional rules
- in-world editing such as placing resources from the viewer
- vector need tradeoffs beyond hunger and thirst
- a full economy with transformation chains, storage logic, carrying, and long-horizon planning

The Streamlit dashboard remains the **experiment console**. The PixiJS viewer is the current **spatial client**.

---

## Immediate Build Priority

The first visible 2D world and the next spatial substrate are now in place. The next major target is **Phase 2: vector needs and a better local decision policy**.

Why this is next:

- the world now has enough topology to create real access differences
- agents can already be seen routing around blocked tiles and slower terrain
- the next missing piece is not visibility, but richer decision pressure

What this means:

- replace the current hunger/thirst-only heuristic with a small need vector
- add energy or fatigue as a movement consequence
- make agents choose actions by expected tension reduction instead of a hard threshold cascade
- keep the viewer focused on legibility while those decision rules become more complex

---

## Running the Simulation

### Setup
GAIA currently requires **Python 3.10+**. The current implementation has been verified with **Python 3.10.20**.

```bash
pip install -r requirements.txt
```

### Command line
```bash
python main.py --days 300 --households 1 --members 20
```
This writes simulation outputs to a JSON file.

### Interactive dashboard
```bash
streamlit run gaia_visualizer.py
```
The Streamlit dashboard is designed as an experiment interface rather than a control panel.
It allows repeatable simulation runs with adjustable parameters and visualizes system-level dynamics over time, supporting inspection, comparison, and future policy experimentation.
At the current stage it is still a **post-run visualization tool**, not a live 2D world.

### PixiJS 2D viewer
The first visible spatial prototype now lives in `viewer/`, and it supports both replay mode and live stepping.

Fastest path from the repo root:

```bash
./run_spatial_world.sh
```

That one command:

- installs the viewer dependencies if needed
- starts the live Python spatial service
- starts the PixiJS viewer on a fixed local port
- shuts both down together when you press `Ctrl-C`

You can override the defaults with environment variables such as `GAIA_GRID_WIDTH`, `GAIA_GRID_HEIGHT`, or `GAIA_MEMBERS`.

Example:

```bash
GAIA_MEMBERS=10 GAIA_GRID_WIDTH=24 GAIA_GRID_HEIGHT=16 ./run_spatial_world.sh
```

If you want to run the pieces manually, install the local viewer dependencies:

```bash
cd viewer
npm install
```

Export a spatial replay artifact from Python:

```bash
python main.py --mode spatial_v1_prototype --days 120 --households 1 --members 6 --grid-width 18 --grid-height 12 --artifact --out viewer/public/demo-spatial.json
```

Or start the live Python service:

```bash
python spatial_live_service.py --port 8765 --days 240 --households 1 --members 6 --grid-width 18 --grid-height 12
```

Run the PixiJS viewer:

```bash
cd viewer
npm run dev
```

Then open the local URL printed by Vite, usually:

```text
http://127.0.0.1:4173/
```

What the PixiJS viewer currently supports:

- replaying a deterministic spatial artifact
- connecting to a live Python stepping service
- rendering terrain tiles, blocked chokepoints, and node stock changes
- play / pause / step / reset controls
- timeline scrubbing
- selected-agent inspection
- loading a different artifact file from disk

This viewer is intentionally a **renderer only**. Python remains the source of truth for world state and movement.

## Status

GAIA is an early-stage research prototype (current version: v0.2).

The current implementation focuses on establishing a modular simulation environment with explicit assumptions, agent-based dynamics, and observable system behavior. Many components are intentionally simplified, with the expectation that they will be extended, refined, or modularized further as new allocation mechanisms and learning agents are introduced.

The immediate roadmap priority is to turn this first visible spatial prototype into a **better live development tool** before moving deeper into economic complexity.

That first visible spatial prototype now exists as a separate PixiJS viewer backed by a minimal Python spatial mode and a live stepping service.

Its value lies in:
- making assumptions explicit,
- producing non-trivial dynamics,
- and serving as a foundation for experimentation with decision-making systems.
