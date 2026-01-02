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

## Running the Simulation

### Setup
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

## Status

GAIA is an early-stage research prototype (current version: v0.2).

The current implementation focuses on establishing a modular simulation environment with explicit assumptions, agent-based dynamics, and observable system behavior. Many components are intentionally simplified, with the expectation that they will be extended, refined, or modularized further as new allocation mechanisms and learning agents are introduced.

Its value lies in:
- making assumptions explicit,
- producing non-trivial dynamics,
- and serving as a foundation for experimentation with decision-making systems.
