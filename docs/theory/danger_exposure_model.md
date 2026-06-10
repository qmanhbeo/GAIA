# Danger: Environmental Exposure Model

## Why Danger Matters

> "Safe" is empty until the world can hurt the agent.

Before Patch 6, GAIA's simulation had five physiological pressures:

- hunger
- thirst
- fatigue
- movement cost
- carried-load fatigue

plus resource depletion (food/water) and home rest — but **no danger**. An agent could wander forever without ever being harmed by the world itself. Rest was a mechanical optimization without a survival motive.

Danger makes "safe rest" meaningful. Without danger, there is no reason to prefer one rest site over another. With danger, shelter, camps, fire, group cohesion, and territorial knowledge become genuine strategic concerns.

## Layer 1 — Environmental Exposure

Exposure is the accumulated burden of being outside protection. It is GAIA's first danger primitive.

**Examples of what exposure represents:**

- heat
- cold
- wetness / rain
- wind
- darkness
- altitude
- rough terrain
- poor air quality

These are aggregated into a single scalar: `agent.exposure`.

## Layer 2 — Biological Ecosystem Danger (deferred)

Examples of what this layer would represent:

- wildlife
- predators
- insects
- disease vectors
- food webs
- ecosystem dynamics

## Layer 3 — Social Danger (deferred)

Examples of what this layer would represent:

- theft
- conflict
- exclusion
- violence
- trust failure

## Current Model (Patch 6 — inert scaffold)

- `agent.exposure` starts at `0.0`
- exposure **increases** when the agent is away from home (`+0.01` per tick by default)
- exposure **recovers** when the agent is at home (`−0.02` per tick by default)
- exposure is clamped to `[0.0, 1.0]`
- `avg_exposure` and `max_exposure` are observable in time-series metrics and UI panels
- **Exposure is inert:** no damage, no decision impact, no rest-quality effect, no camp protection

## What NOT to Build (current boundary)

- Do not implement wildlife yet.
- Do not implement predators yet.
- Do not implement disease yet.
- Do not implement social danger yet.
- Do not activate camp rest yet.
- Do not make camps reduce exposure yet.
- Do not make exposure damage health yet.
- Do not make exposure affect decisions yet.

## Why Exposure Comes First

Exposure was chosen as GAIA's first danger primitive because:

1. **Primitive and general.** A single scalar can later decompose into heat, cold, wetness, wind, darkness, terrain harshness, and altitude. It is the simplest possible "world hurts you" mechanic.

2. **Low implementation cost.** Exposure is a single float, a per-tick accumulator, and a few configuration knobs. No new agent types, no spatial AI, no combat model.

3. **Natural connections.** Exposure connects directly to shelter, fire, clothing, camps, group cohesion, and home. It provides immediate motivation for everything layer-1 survival already demands.

4. **Observability before behavior.** Making exposure visible in metrics and panels before it does anything gives developers and future agents a lever to learn from.

5. **Phased growth.** The same pattern used for fatigue (inert scaffold → recovery → activity sensitivity → behavioral response → observability) applies to exposure and all future dangers.

## Why Wildlife Is Deferred

Wildlife would require:

- ecosystem agents with movement, reproduction, and life cycles
- predator/prey behavior
- food webs and trophic dynamics
- injury, combat, or avoidance mechanics
- possible disease vectors

That is an entire ecosystem simulator layered on top of GAIA before GAIA's core survival loop is complete. Wildlife belongs in Layer 2, after the layer-1 environmental model has working protection, shelter, camps, and observable danger pressure.

## Future Path

1. Exposure exists and is observable (Patch 6 — done).
2. Tile-specific `exposure_pressure` appears (some tiles expose more than others).
3. Home, camps, shelter, fire, and group proximity provide exposure protection.
4. Exposure modifies rest quality (higher exposure → worse rest).
5. Extreme exposure can damage health (the first real danger consequence).
6. Agents learn to seek protection when exposed.
7. Camps become meaningful rest and protection sites.
8. Wildlife and ecosystem danger arrive (Layer 2) — only after layer-1 environmental danger is mature.
