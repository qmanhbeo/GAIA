# Survival Buffer Economics

## 1. Purpose

GAIA currently has homeostatic agents with task commitment, ETA-aware target
choice, resource stock and depletion mechanics, and fixed homes. The current
decision rule works: agents drink, eat, gather, deposit, and survive repeatably.

The next conceptual step is not money, markets, or exchange. It is explaining
how agents begin to invest in places — camps, storage, shelter, and eventually
migration — without being scripted to do so.

This document defines the concepts that bridge from today's homeostatic
commitment model to tomorrow's settlement, shelter-building, and early economic
utility layer.

It is a design reference for future coding agents, not a simulation science
paper.

## 2. Conceptual anchors

The following ideas inform GAIA's next layer. They are not cited as proof of
correctness but as concise labels for design reasoning.

### Homeostasis and allostasis

- **Homeostasis** (Cannon 1932): immediate negative-feedback correction of
  internal variables — eat when hungry, drink when thirsty.
- **Allostasis** (Sterling & Eyer 1988; McEwen 1998): stability through
  anticipatory change. The agent acts *before* a variable reaches crisis
  because it predicts future need.
- **Allostatic load** (McEwen 2000): the cumulative cost of repeated
  adaptation under stress. Agents that repeatedly cut travel margins,
  skip rest, or eat emergency rations degrade over time.

These concepts already appear in `motivation_model.md`. They are restated here
because survival-buffer economics is essentially *allostatic investment*: the
agent spends resources now to reduce future allostatic load.

### Optimal foraging / patch choice

- Stephens & Krebs (1986): foragers choose patches based on travel cost,
  expected yield, depletion rate, and handling time.
- GAIA's ETA-aware target selection and stock-checking already reflect basic
  patch-choice logic.
- The next step is to extend patch choice from *which food node to visit* to
  *whether to build a camp near this patch* and *whether to move home there*.

### Niche construction

- Laland, Odling-Smee & Feldman: organisms do not only adapt to environments;
  they modify them. Nests, burrows, dams, and storage pits are
  environmentally constructed adaptations.
- A GAIA agent that builds a shelter near a food patch is performing niche
  construction: it changes the survival landscape for its future self.
- Niche construction bridges the gap between foraging behaviour and
  settlement / economic behaviour.

### Boserup / intensification pressure

- Boserup (1965): population and resource pressure drive agricultural
  intensification, not the other way around.
- This is a future anchor. It explains why GAIA should let resource scarcity
  *push* agents toward agriculture and storage investment rather than adding
  agriculture as a scripted upgrade path.

## 3. Translation into GAIA concepts

### Need state (existing and future)

| Variable | Role | Status |
|---|---|---|
| `agent.hunger` | Food deficit | Existing |
| `agent.thirst` | Water deficit | Existing |
| `agent.health` | Viability reserve | Existing |
| Fatigue (future) | Rest deficit | Not yet added |
| Exposure (future) | Environmental damage | Not yet added |

### Homeostatic action

Immediate correction of a need variable with no persistent side effect:

- drink
- eat (at node or at home)
- rest

### Allostatic action

Action taken before crisis to reduce future need or travel cost:

- carry food before hunger is critical
- choose a farther but viable resource node over a closer depleted one
- **build a camp** before exposure season / before a long foraging cycle
- **store food** beyond immediate need
- **move home** before the current location becomes lethal

### Survival buffer

Any stock, structure, location, or relationship that makes future homeostasis
easier or more reliable:

- stored food
- stored water (future mechanic)
- shelter quality (improves rest, reduces exposure damage)
- camp / home location (reduces average travel cost to resources)
- knowledge of resource locations and their depletion state
- reliable path / route (e.g., clearing obstacles between home and water)
- group / cooperation (future layer — not yet)

### Economic utility

GAIA should not use abstract hedonic utility (pleasure, happiness). Instead:

```
utility(action)
  = expected_future_homeostatic_stability_gain
    - immediate_need_cost
    - travel_cost
    - material_cost
    - risk_cost
    - opportunity_cost
```

Where:

- **expected future stability gain** is the reduction in projected allostatic
  load over a planning horizon.
- **immediate need cost** is the hunger/thirst/health penalty of spending time
  on this action instead of eating/drinking.
- **travel cost** is ETA × need-increase-per-tick.
- **material cost** is any resource consumed (e.g., food used to build).
- **risk cost** is the chance of dying during the action (ETA ≥ death_time).
- **opportunity cost** is the best alternative action's projected gain.

This is not executable code. It is a conceptual template for future heuristic
weighting.

### Investment

> Investment = accepting short-term survival cost for longer-term survival-buffer improvement.

An agent that skips one meal to carry building material to a campsite is
investing. An agent that abandons a half-built shelter because hunger became
critical is failing to protect its investment — which is realistic behaviour
that GAIA should preserve.

The key design constraint: **investment must be reversible or incremental**.
An agent should be able to stop halfway through building, eat, then resume.
GAIA should not force a binary commit-or-die choice on construction.

## 4. Shelter as capital

A shelter is not just an object. It is **early physical capital** because it
stores past labour and improves future survival:

- Built shelter is an accumulated survival buffer that exists independently of
  the agent's current physiological state.
- It cannot be carried; the agent must return to it to benefit.
- Its value depends on location: a shelter built between food and water is
  worth more than a shelter built in a dead zone.

Potential shelter effects:

| Effect | Impact |
|---|---|
| Increased rest recovery rate | Fatigue drops faster per tick |
| Reduced or eliminated exposure damage | Health does not decay while inside |
| Increased storage capacity | Home stock cap raised |
| Lower predation / accident risk | Reduced random-event damage |
| Higher psychological stability | Lower critical-override frequency (future) |

Shelter quality should be a continuous variable (e.g., `0.0` to `1.0`) that
can be incrementally improved. Each upgrade costs time and possibly materials.

## 5. Camps before migration

GAIA should add **camps** before full home-relocation.

A camp is a lightweight, temporary node associated with an agent:

- Smaller storage cap than home
- Lower or zero shelter quality by default
- Can be created near a resource patch
- Can be upgraded incrementally
- May decay or be abandoned if unused
- Does not replace the home; it is an auxiliary node

Why camps first:

1. **Camps are reversible.** An agent can try camping without abandoning its
   home. If the camp fails (no food nearby), the agent returns home with
   minimal loss.
2. **Camps generate the data needed for migration decisions.** Once an agent
   has spent 50 ticks at a camp, it has empirical experience of that
   location's survival-buffer value. It can compare that with the home
   location's value.
3. **Camps are a natural upgrade target.** A well-placed camp with a good
   shelter is effectively a new home candidate. The transition from camp to
   home is a threshold on accumulated upgrades, not a flag day.
4. **Camps explain resource competition.** Multiple agents building camps
   near the same food patch creates implicit pressure to either cooperate,
   compete, or disperse — without adding a single line of social logic.

## 6. Migration decision

Migration should not be scripted. It should emerge when the agent's own
experience shows that another location has higher survival-buffer value than
the current home.

Core comparison:

```
new_site_value > old_home_value + moving_cost
```

Where site value depends on:

- Food access: average travel ETA to the nearest food node with reliable stock
- Water access: average travel ETA to the nearest water node
- Resource depletion risk: number of competing agents / depletion frequency
- Shelter quality: accumulated camp upgrades
- Storage capacity: food and water that can be stored
- Safety: exposure, predation risk, distance from hazards
- Expected regeneration: how fast local resources replenish
- Memory confidence: how many empirical observations support the estimate

### Moving cost

Migration should not be free. The cost includes:

- Travel time to move all stored goods
- Lost shelter investment at the old home (partial or total)
- Risk during transit (ETA may exceed remaining survival time)
- Opportunity cost of not foraging during the move

### Latching migration

The same hysteresis principle that prevents task oscillation should prevent
home oscillation. The threshold to *abandon* a home should be higher than the
threshold to *try* a camp. This prevents agents from migrating every time a
resource ticks below a threshold.

A practical heuristic:

```
migrate when:
  camp_value - home_value > moving_cost + uncertainty_margin
```

Where `uncertainty_margin` grows with low memory confidence (few observations)
and shrinks with high confidence (many successful foraging cycles at the camp).

## 7. Implementation implications

The following steps are listed conceptually. They are not implementation
instructions for the current session.

1. **Make depletion ecologically meaningful.** Reduce resource capacities and
   replenish rates so that depletion actually happens and agents must choose
   between depleted and viable patches. Current physiology makes food and
   water effectively infinite.

2. **Add resource memory.** Agents remember the last-seen stock of each node
   they have visited. This lets them avoid travelling to a node they know is
   depleted.

3. **Add `CampNode`.** A lightweight node that an agent can create on any
   passable tile. Has `storage_capacity`, `shelter_quality`, and a decay
   timer.

4. **Allow deposit and rest at camp.** Agents can store food at a camp and
   rest there. Rest recovery rate depends on `shelter_quality`.

5. **Add `shelter_quality` as an upgradeable continuous variable.** Range
   `0.0` (no shelter) to `1.0` (fully built). Each upgrade tick consumes
   time and possibly materials (carried food).

6. **Add camp upgrade action.** The agent spends time at camp to increase
   `shelter_quality`. This is the first *investment* action that does not
   immediately satisfy a need.

7. **Add `site_value` estimate.** A heuristic computed from local food
   access, water access, shelter quality, and memory confidence.

8. **Allow home relocation.** Only after a camp has been used for N
   consecutive ticks and its computed site value exceeds the current home's
   value by a threshold. The old home becomes an unowned node or decays.

9. **Later: agriculture.** When wild food nodes are persistently depleted,
   agents may invest in planting or protecting food sources near their camp.
   This should emerge, not be scripted.

10. **Much later: exchange / money.** Only after settlement, storage,
    specialisation, and surplus exist naturally. Money is a solution to a
    coordination problem that does not yet exist in GAIA.

## 8. Non-goals (explicitly deferred)

The following are not part of survival-buffer economics and should not be
designed or implemented in the next phase:

- No money, currency, or credit.
- No markets, prices, or exchange rates.
- No property rights, ownership titles, or inheritance.
- No full agricultural cycle (planting, growth, harvest).
- No global logistics or supply chains.
- No society-level simulation (government, law, war).
- No explicit kinship, marriage, or reproductive dynamics.
- No utility function based on pleasure, happiness, or welfare.

All of these become relevant later, but only after basic survival-buffer
investment works reliably.

## 9. Design principle

> GAIA should not add civilisation features directly. It should add survival
> pressures and survival buffers, then let settlement, migration, storage,
> shelter, and eventually economic coordination emerge as adaptive responses
> to those pressures.

## References

- Cannon, W. B. (1932). *The Wisdom of the Body*. — homeostasis concept.
- Sterling, P. & Eyer, J. (1988). "Allostasis: a new paradigm to explain
  arousal pathology." — anticipatory regulation.
- McEwen, B. S. (1998). "Protective and damaging effects of stress mediators."
  *New England Journal of Medicine*. — allostatic load.
- Stephens, D. W. & Krebs, J. R. (1986). *Foraging Theory*. — patch choice
  and optimal foraging.
- Laland, K. N., Odling-Smee, F. J. & Feldman, M. W. (2000). "Niche
  construction, biological evolution, and cultural change." — organisms
  modify environments as an adaptive strategy.
- Boserup, E. (1965). *The Conditions of Agricultural Growth*. — population
  pressure drives intensification, not the reverse.
