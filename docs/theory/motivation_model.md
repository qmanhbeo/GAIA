# GAIA Motivation Model

## 1. Why this exists

A systematic audit of the spatial GAIA simulation exposed a fundamental
survival failure: agents routinely perished from starvation and dehydration
despite abundant food and water nodes on the same grid.

Key findings from that audit:

- **Zero drink events** appeared across multi-hundred-tick runs.
- **Water stock remained untouched** — the resource node was present but never
  visited.
- **Agents oscillated** between food, water, and home targets, re-evaluating
  their intent every tick and aborting mid-route as soon as a competing
  physiological variable crossed a nearby threshold.
- Only a single gather-deposit cycle was ever completed in a 20-agent × 200-
  tick run; all other agents died while walking back and forth.

The problem is not resource scarcity. It is a failure of **action selection
and execution**: the decision rule lacks behavioral persistence and cannot
commit to a survival task long enough to reach its destination.

This document outlines the theoretical framework for the next-generation
decision rule.

## 2. Theoretical foundation

### Homeostasis

Biological organisms maintain internal physiological variables within narrow
survivable bounds through negative-feedback loops. A GAIA agent must
similarly sense deviations in hunger and thirst and execute corrective
actions. The simplest homeostatic controller is a setpoint with a tolerance
band: act when the variable drifts outside the band, stop when it returns.

### Allostasis

Reactive homeostasis waits until a variable is already critical. Allostasis
extends this with **prediction**: the agent estimates its future state based
on current decay rates, travel time to resources, and expected consumption
gain. An allostatic agent leaves for the water node while it is still
moderately thirsty, because it knows the journey will take 10 ticks and
thirst will rise by 0.41 during that time.

### Homeostatic Reinforcement Learning (HRL)

HRL formalises action value as **projected drive reduction**. Drive is the
distance from an optimal setpoint in a multidimensional physiological space.
The value of travelling to a food node is the reduction in drive expected
after travel and consumption, discounted by travel cost. This grounds utility
in the agent's own physiology rather than in arbitrary reward numbers.

### Bounded rationality

Agents cannot evaluate every possible action sequence at every tick. Under
bounded rationality they must "satisfice" — select actions that are good
enough to maintain viability under time and computational constraints. This
implies limiting the frequency of pathfinding, re-using existing plans, and
accepting locally optimal decisions.

### BDI intention and commitment

The Belief-Desire-Intention (BDI) model distinguishes between vague desires
("I should drink sometime") and concrete intentions ("I am walking to the
water node at grid 20,10"). Once an intention is formed, the agent commits
to it, filtering out competing desires unless a critical override fires.
This prevents the agent from reversing course every time a marginal
physiological threshold is crossed.

### Latching / hysteresis

In electronic circuits, a Schmitt trigger uses hysteresis to prevent rapid
switching near a threshold. The same principle applies to action selection:
the threshold for *abandoning* a current task should be higher (or stricter)
than the threshold for *starting* it. This creates a stable latch that
resists oscillation.

### Maslow as background intuition, not a rigid hierarchy

Maslow's hierarchy correctly recognises that survival needs are urgent and
deprioritise higher goals when resources are scarce. However, a rigid
pyramid with hard priority gates is biologically unsupported. Needs interact
continuously: an agent can be hungry and thirsty simultaneously, and the
correct response is a trade-off based on urgency, travel cost, and resource
availability, not a strict "food first, water second" stack.

GAIA does **not** implement a Maslow pyramid. Maslow serves only as an
intuitive reminder that physiological needs dominate — but they do so through
a continuous utility trade-off, not through priority gates.

## 3. Design principle

> GAIA agents are modelled as bounded homeostatic controllers. They choose
> survival tasks based on physiological urgency, estimated travel time, and
> resource availability. Once committed to a task, they maintain it until
> completion unless another need is predicted to become critical before the
> current task finishes.

## 4. Mapping to current GAIA code

| Variable | Meaning | Direction |
|---|---|---|
| `agent.hunger` | Energy deficit | Higher = worse |
| `agent.thirst` | Hydration deficit | Higher = worse |
| `agent.health` | Viability reserve | Decays when hunger or thirst is extreme |
| `agent.carried_food` | Food carried from node to home | 0 → capacity |
| `home.stock` | Stored food at agent's home | 0 → capacity |
| `food_node.stock` | Renewable food at grid food node | Replenishes per tick |
| `water_node.stock` | Renewable water at grid water node | Replenishes per tick |
| `agent.state` | Current behavioural state | String label |
| `agent.last_action` | Last action taken | String label |
| `agent.(x,y)` | Grid position | — |
| `agent.target_id` | Current target node id | Set each tick |
| `engine.events` / `engine.event_log` | Behavioural trace | Per-tick + cumulative |

No variable renames or semantic inversions are proposed at this stage.

## 5. Proposed next implementation model

The following describes the conceptual shape of the next decision rule
without specifying exact thresholds or implementation details.

### Lightweight commitment fields

Add to `SpatialAgent`:

```python
current_task: str | None = None
task_target_id: str | None = None
task_started_tick: int | None = None
```

### Task vocabulary

```
seek_water              travel to water node, drink on arrival
seek_food               travel to food node, gather or eat on arrival
return_home_with_food   travel home carrying food, deposit on arrival
eat_at_home             consume home-stored food
eat_at_node             consume food at food node (emergency)
deposit_food            store carried food into home
rest                    idle at home (slow health regen)
```

### Decision rule outline (next version)

1. **Continue current task** if `current_task` is set, the task target still
   exists and has available stock, and no other need has crossed a critical
   override threshold since the task was started.

2. **Reconsider when:**
   - The current task is completed (arrival + consummatory action done).
   - The target resource has been depleted by another agent.
   - A competing physiological variable has crossed a **critical override**
     threshold (e.g., thirst is below a hard danger line even while seeking
     food).
   - The agent has been travelling for too long relative to its projected
     decay and may not survive the round trip.

3. **Select next task** by estimating the projected homeostatic state after
   travel + consumption for each candidate, and choosing the one that
   maximises drive reduction discounted by travel time.

### Latching effect

The combination of commitment (don't re-evaluate every tick) and critical
overrides (do re-evaluate when truly necessary) produces hysteresis. A
marginal shift in hunger below 0.5 will **not** trigger a target switch if
the agent is already walking to water — but thirst hitting a hard floor
(e.g., `health` dropping below 0.3) will override any current task.

## 6. Anti-patterns to avoid

| Anti-pattern | Why |
|---|---|
| Rigid Maslow pyramid | Prevents multi-objective trade-offs and adaptive behaviour |
| Naive tick-by-tick switching | Causes oscillation; agents die before reaching any resource |
| Perfect global optimisation | Computationally intractable; violates bounded rationality |
| Arbitrary utility functions | No physiological grounding; hard to calibrate |
| Premature reinforcement learning | Need a reliable deterministic baseline before adding learning |
| Massive ECS/plugin rewrite | The fix is localised to the decision rule; no architectural overhaul needed now |

## 7. Next implementation acceptance criteria

The next behaviour patch should pass these tests:

1. An agent seeking water does **not** abandon the water target merely
   because hunger crosses a mild threshold (e.g., 0.5) mid-route.

2. An agent seeking food does **not** abandon the food target merely because
   thirst crosses a mild threshold (e.g., 0.5) mid-route.

3. An agent **does** abandon a task if another need becomes critical
   (e.g., `health` dropping below a danger threshold, or a variable reaching
   a starvation level that will kill before the current task completes).

4. At least one `drink` event appears naturally in a 200-tick run.

5. `water_node.stock` decreases measurably in a 200-tick run with 20 agents.

6. Target switching frequency drops by at least 5× compared with the current
   behaviour (measured as total intention switches ÷ total ticks).

7. Agents no longer all die while water and food nodes remain untouched.
   At least one agent survives a 200-tick run.
