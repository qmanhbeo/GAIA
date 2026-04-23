# GAIA Roadmap: Topological Tension Economy

## Summary

GAIA should evolve from a centralized survival simulator into a **2D spatial research laboratory** for non-price economic coordination. The next major architecture will model economics as **agents navigating a constrained terrain of deficits, affordances, queues, and transformation chains**, not as prices or equal distributions.

Defaults locked for this roadmap:
- **World model:** discrete **2D tile grid**
- **Primary acting unit:** **individual members**
- **Baseline institution:** **commons + queue**
- **Primary goal:** **research lab**, not game-first polish
- **Simulation stack:** custom **Python core**
- **Research console:** **Streamlit**
- **Future 2D renderer:** **PixiJS** in the browser once the spatial world exists
- **RL interfaces later:** **Gymnasium** first, **PettingZoo** if the environment is exposed as a true multi-agent API
- **RL timing:** **defer RL** until the environment has real scarcity, contention, topology, and measurable tradeoffs

Additional stack decisions:
- **Do not** use Streamlit as the permanent game surface
- **Do not** adopt Mesa as the core architecture
- **Do not** target Godot unless the project pivots toward a full game product

## Immediate Priority

The first visible 2D world and the next spatial substrate are now implemented. The next implementation target is **Phase 2: vector needs and a better local decision policy**.

Reasoning:
- the map now has terrain, blocked tiles, pathfinding, and physical node access
- the current bottleneck is no longer “can we see the world?”
- the next bottleneck is “are the agents making interesting enough tradeoffs inside that world?”

Near-term focus:
- extend the need model beyond hunger and thirst
- add energy or fatigue as a movement consequence
- move from hard thresholds toward interpretable tension-based local action choice
- keep the viewer legible while the policy layer becomes richer

## Key Architectural Changes

### 1. Replace centralized allocation with a world model

Introduce a persistent world state that owns:
- a 2D tile grid with terrain, movement cost, passability, and occupancy limits
- spatial resource nodes with inventories, replenishment rules, queue capacity, and access rules
- agent positions, inventories, needs, capabilities, and current intentions
- a deterministic clock with explicit action resolution phases

Required public interfaces:
- `WorldConfig`: grid size, terrain defaults, movement costs, occupancy rules, seed, tick duration
- `WorldState`: tiles, agents, households, nodes, queues, metrics, current tick
- `ResourceNode`: node type, position, stock, replenishment, extraction rate, access policy
- `AgentState`: position, alive flag, household id, need vector, health, energy, inventory, skill/capability traits
- `SimulationEngine.step()`: advance one tick using explicit phase ordering
- `SimulationEngine.snapshot()`: return a structured state summary for UI and experiments

### 2. Replace scalar survival with vector tensions

Model each agent as a vector of tensions instead of a single “value” number.

Initial need axes:
- food
- water
- energy/fatigue
- safety
- future security buffer

Rules:
- all actions must improve at least one axis while potentially worsening others
- movement consumes energy and time
- unmet needs degrade health on different schedules
- agents select actions using a tension-reduction heuristic, not a price/profit rule

Required interfaces:
- `NeedVector`
- `ActionCandidate`
- `DecisionPolicy.evaluate(world, agent) -> ranked actions`
- `ActionResolver.apply(action, world)`

### 3. Make resources into topological wells with access walls

Resources are no longer passive stock counters. They become spatial affordances with extraction friction.

Baseline node types for the first spatial economy:
- water well
- farm field
- household storage
- rest/shelter point

Required behavior:
- each node has finite throughput per tick
- each node can be depleted and replenished
- access is constrained by path distance, queue length, and extraction time
- queues are first-come-first-served in the baseline commons regime
- queueing and congestion impose real opportunity costs through time and energy loss

### 4. Separate production, movement, access, and institutions

The engine should explicitly separate:
- movement through space
- access to a node
- extraction/consumption
- transformation of inputs into outputs
- institutional rules that gate or prioritize access

Initial institution set:
- `CommonsQueueAccessPolicy` as the default baseline
- later comparison policies: need-priority, quotas, reservations, permits

### 5. Build observability before RL

The environment must become measurable before any learning layer is added.

Required metrics:
- unmet tension by axis
- deaths by cause
- queue wait time
- travel distance and travel energy
- extraction throughput by node type
- congestion hotspots
- inequality of access and outcome across households
- stock, depletion, waste, and replenishment
- “systemic heat” proxy: total wasted movement/time/idle queueing under unmet need

The Streamlit layer should evolve into an experiment console with:
- grid rendering
- tension heatmaps
- node utilization maps
- queue/congestion overlays
- tick replay or sampled snapshots
- scenario comparison runs under different institution settings

## Roadmap Checklist

### Phase 0: Stabilize v0.2 into a clean baseline
- [x] Freeze the current v0.2 model as a legacy baseline for comparison
- [x] Extract tunable assumptions into structured config objects instead of loose constants only
- [x] Define deterministic seeding and reproducible run outputs
- [x] Add a metrics schema for all future runs
- [x] Add basic automated tests around current engine stepping and logging

Acceptance criteria:
- the current simulation still runs unchanged as a baseline mode
- seeded runs produce repeatable metric series
- future versions can be compared against v0.2 on shared metrics

### Phase 1A: First Visible 2D World
- [x] Add a fixed tile grid with simple rendering-friendly state
- [x] Give agents and resource nodes `(x, y)` coordinates
- [x] Add one household/home location, one food node, and one water node to a simple scenario
- [x] Add a minimal movement rule: agents move one step per tick toward the highest-priority reachable need target
- [x] Expose live stepping, auto-run, and replay in the UI
- [x] Show per-agent stats in the UI while the world is running

Acceptance criteria:
- you can watch agents move on a 2D grid
- agent locations update every tick
- at least food and water seeking are visible in the movement pattern
- the UI can step the world slowly enough for human inspection
- this slice is usable for behavioral intuition even if institutions and advanced logic are still absent

### Phase 1B: Spatial world primitives
- [x] Add a tile grid abstraction with coordinates, terrain types, movement costs, and occupancy rules
- [x] Give agents, households, and nodes positions in the world
- [x] Add pathfinding or shortest-path movement cost calculation on the grid
- [x] Replace direct food/water distribution with explicit travel and access attempts
- [x] Preserve daily/tick stepping through the existing engine entrypoint

Decisions locked:
- use a discrete tile grid, not a node graph
- keep world stepping turn-based/deterministic rather than continuous-time
- households remain social/storage groupings; individuals are the moving actors

Acceptance criteria:
- an agent must physically move to a node before extracting a resource
- distance and terrain affect access outcomes
- stockpiles no longer explode solely because distribution is free

### Phase 2: Implement vector needs and agent decision policy
- [ ] Replace simple hunger/hydration logic with a need vector and explicit decay rules
- [ ] Add energy cost for movement, waiting, and labor
- [ ] Add a baseline local decision policy that chooses actions by expected tension reduction per unit effort/time
- [ ] Add inventory carrying limits so movement and hauling matter
- [ ] Add “do nothing/rest” as a valid action when beneficial

Decisions locked:
- no universal scalar “value”
- action choice is local and heuristic first, not global optimization
- the first policy is interpretable and hand-authored, not learned

Acceptance criteria:
- agents visibly trade off one need axis against another
- agents can get trapped by topology or timing, not just by low stocks
- behavior logs explain why each chosen action was preferred

### Phase 3: Add commons institutions and contention mechanics
- [ ] Implement queue objects and node throughput limits
- [ ] Enforce first-come-first-served access in the default commons regime
- [ ] Add occupancy-driven congestion penalties on heavily used paths or tiles
- [ ] Track denied access, idle waiting, and abandonment of queues
- [ ] Add household storage behavior and local return-to-home loops

Decisions locked:
- the first institutional baseline is commons + queue
- no ownership, prices, or trade in the first spatial economy
- contention is resolved through time and throughput, not hidden random allocation

Acceptance criteria:
- crowding at one well or farm creates measurable wait times and opportunity cost
- path congestion can make a farther node preferable
- institution metrics can explain failures without using prices

### Phase 4: Add transformation chains and future-oriented behavior
- [ ] Introduce transformation recipes such as seed + labor + time -> crop
- [ ] Separate raw resource extraction from production and consumption
- [ ] Add delayed outcomes so some actions improve future security rather than immediate need
- [ ] Add simple capability differences such as carry capacity, farming efficiency, or recovery rate
- [ ] Add household-level planning for storage and risk buffering while individuals still execute actions

Decisions locked:
- transformation chains are mandatory before RL
- future security remains a modeled tension axis
- households coordinate storage and resilience, but individuals remain the execution unit

Acceptance criteria:
- agents face meaningful short-term vs long-term tradeoffs
- the economy can enter poverty traps or recover depending on topology and rules
- production bottlenecks are visible in metrics and map overlays

### Phase 5: Build experiment tooling and comparison harness
- [ ] Define scenario files for world layout, node placement, terrain, population, and institutions
- [ ] Add batch run support for repeated seeded scenarios
- [ ] Add comparison reports across institution variants
- [ ] Add visual outputs for heatmaps, queue plots, and node utilization
- [ ] Add canonical benchmark scenarios

Canonical scenarios:
- local abundance
- distant abundance
- single-well congestion
- dual-resource tradeoff
- seasonal scarcity
- poverty trap recovery

Acceptance criteria:
- one command can run a scenario suite and output comparable metrics
- the visualizer can show both time-series and spatial state
- institution changes can be evaluated on the same map and seed family

### Phase 6: Prepare RL-ready environment boundaries
- [ ] Define an intervention API for a planner/controller separate from agent logic
- [ ] Restrict early intervention actions to terrain and institution changes, not direct per-agent control
- [ ] Expose observation tensors or structured summaries suitable for RL later
- [ ] Define reward families centered on systemic tension, throughput, resilience, and waste
- [ ] Add offline “shadow evaluation” where planner actions can be tested against benchmark scenarios

Decisions locked:
- RL acts as a topological/institutional engineer, not as the agent brain
- RL is introduced only after the benchmark scenarios expose non-trivial tradeoffs
- the environment must support both hand-authored institutions and learned planners

Acceptance criteria:
- a planner can modify roads, barriers, capacities, or access rules through a stable interface
- no planner is required for the environment to be meaningful
- RL integration can begin without reworking the world model

### Phase 7: RL phase after environment maturity
- [ ] Start with offline or episodic interventions, not per-tick micromanagement
- [ ] Train on benchmark scenarios with fixed seeds and held-out layouts
- [ ] Compare learned planners against hand-authored institution baselines
- [ ] Measure whether the planner reduces systemic heat without simply shifting suffering between agents
- [ ] Add generalization tests across unseen topologies and scarcity regimes

Success criteria:
- RL improves benchmark metrics over commons baseline on more than one scenario family
- improvements persist on held-out maps
- learned behavior remains interpretable enough to audit

## Public API / Interface Changes

These interfaces should be considered part of the new contract and designed deliberately before implementation:
- `run_simulation(config)` should accept structured config, not only CLI scalars
- simulation output should include both time-series metrics and optional spatial snapshots
- scenario definition format should include map layout, node placement, population, and institution
- the visualizer should support both live stepping and recorded run artifacts
- institutions must be pluggable policies with a stable access-resolution interface
- planner/RL hooks must be optional and isolated from core agent decision logic

CLI expectations:
- retain the current simple CLI for legacy mode
- add scenario-driven CLI entrypoints for spatial mode
- support seed, scenario id, output path, and snapshot frequency

## Test Plan

### Deterministic engine tests
- fixed seed produces identical trajectories
- pathfinding cost matches terrain rules
- queue ordering is stable and auditable
- node throughput and replenishment obey config limits

### Behavior tests
- hungry agent chooses nearer food over farther food when other tensions are equal
- thirsty agent abandons food trip if water tension crosses a critical threshold
- congestion causes route switching or waiting behavior
- carrying limits prevent infinite extraction loops

### Institution tests
- commons queue enforces first-come-first-served access
- capacity limits create measurable wait time without violating stock accounting
- alternative policies can be swapped without changing core world logic

### Scenario tests
- single-node scarcity creates queues and unmet needs
- dual-node map with different distances creates local economies
- seasonal or replenishment shocks alter movement patterns and outcomes
- poverty trap scenario is possible and recoverable under at least one improved topology

### RL-readiness tests
- planner action interface can alter terrain or access rules without corrupting state
- observation export is stable across repeated runs
- benchmark suite produces metrics suitable for optimization and comparison

## Assumptions and Defaults

- This roadmap is for a **research simulation**, not a commercial game
- The first serious world is **2D tile-based**, not graph-based
- Individuals act directly; households provide storage and social structure
- The baseline economy is **non-price, commons-based, and queue-mediated**
- No markets, money, ownership, or barter are required before the spatial model is working
- RL is out of scope until topology, contention, and delayed production are implemented
- Streamlit remains the primary **lab console** until the spatial viewer needs justify a separate client
- PixiJS is the intended browser renderer once live 2D visualization outgrows Streamlit
- The legacy v0.2 mode remains available for comparison until the new model fully supersedes it
