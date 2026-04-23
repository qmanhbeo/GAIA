import "./style.css";
import * as PIXI from "pixi.js";

const DEFAULT_ARTIFACT_PATH = "/demo-spatial.json";
const TICK_MS_FALLBACK = 280;

const state = {
  artifact: null,
  frames: [],
  frameIndex: 0,
  playing: true,
  tickDurationMs: TICK_MS_FALLBACK,
  selectedAgentId: null,
  accumulatorMs: 0,
  sprites: new Map(),
  nodeSprites: new Map(),
};

const appRoot = document.querySelector("#app");
appRoot.innerHTML = `
  <div class="shell">
    <main class="workspace">
      <section class="brandline">
        <div class="brand-copy">
          <div class="micro-tag">GAIA Spatial Prototype</div>
          <h1>First visible world</h1>
          <p>Python remains authoritative. This viewer only replays spatial snapshots so movement and need-driven behavior can be inspected before deeper economics arrive.</p>
        </div>
      </section>

      <section class="meta-grid">
        <article class="metric">
          <div class="metric-label">Tick</div>
          <div class="metric-value" id="metric-tick">0</div>
        </article>
        <article class="metric">
          <div class="metric-label">Population</div>
          <div class="metric-value" id="metric-population">0</div>
        </article>
        <article class="metric">
          <div class="metric-label">Avg Hunger</div>
          <div class="metric-value" id="metric-hunger">0.00</div>
        </article>
        <article class="metric">
          <div class="metric-label">Avg Thirst</div>
          <div class="metric-value" id="metric-thirst">0.00</div>
        </article>
      </section>

      <section class="stage" id="stage">
        <div class="stage-overlay"></div>
      </section>

      <section class="controls">
        <button class="btn" id="play-toggle">Pause</button>
        <button class="btn" id="step-btn">Step</button>
        <label class="file-label">
          Load artifact
          <input id="artifact-input" type="file" accept="application/json" />
        </label>
        <div class="timeline-wrap">
          <input id="timeline" type="range" min="0" max="0" step="1" value="0" />
          <span id="timeline-label">0 / 0</span>
        </div>
        <button class="btn" id="reset-btn">Reset</button>
      </section>
    </main>

    <aside class="sidebar">
      <section class="panel">
        <h2>Run Status</h2>
        <div class="status-line"><span>Viewer</span><strong id="viewer-mode">loading</strong></div>
        <div class="status-line"><span>Engine</span><strong id="engine-version">unknown</strong></div>
        <div class="status-line"><span>Seed</span><strong id="seed-value">-</strong></div>
      </section>

      <section class="panel">
        <h2>Selected Agent</h2>
        <div id="agent-card" class="hint">Click an agent or let the default selection load.</div>
      </section>

      <section class="panel">
        <h3>Legend</h3>
        <div class="legend-grid">
          <div class="legend-item"><span class="legend-swatch" style="background:#ffdd9a"></span>Home / rest point</div>
          <div class="legend-item"><span class="legend-swatch" style="background:#9df584"></span>Food node</div>
          <div class="legend-item"><span class="legend-swatch" style="background:#76d0ff"></span>Water node</div>
          <div class="legend-item"><span class="legend-swatch" style="background:#f6f8fb"></span>Agent body</div>
          <div class="legend-item"><span class="legend-swatch" style="background:#f5b156"></span>Selected agent highlight</div>
        </div>
      </section>

      <section class="panel">
        <h3>Use</h3>
        <div class="hint">
          Export a deterministic replay from Python, then load it here. The frontend only draws snapshots and never decides movement.
        </div>
      </section>
    </aside>
  </div>
`;

const stageElement = document.querySelector("#stage");
const timelineInput = document.querySelector("#timeline");
const timelineLabel = document.querySelector("#timeline-label");
const playToggle = document.querySelector("#play-toggle");
const stepButton = document.querySelector("#step-btn");
const resetButton = document.querySelector("#reset-btn");
const artifactInput = document.querySelector("#artifact-input");

const pixiApp = new PIXI.Application();
await pixiApp.init({
  resizeTo: stageElement,
  antialias: true,
  backgroundAlpha: 0,
  resolution: window.devicePixelRatio || 1,
});
stageElement.prepend(pixiApp.canvas);

const worldRoot = new PIXI.Container();
const trailLayer = new PIXI.Container();
const gridLayer = new PIXI.Container();
const nodeLayer = new PIXI.Container();
const agentLayer = new PIXI.Container();
worldRoot.addChild(trailLayer, gridLayer, nodeLayer, agentLayer);
pixiApp.stage.addChild(worldRoot);

const queryArtifact = new URLSearchParams(window.location.search).get("artifact");
const artifactPath = queryArtifact || DEFAULT_ARTIFACT_PATH;

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function safeValue(value, fallback = 0) {
  return Number.isFinite(value) ? value : fallback;
}

function meterRow(label, value, color) {
  const clamped = clamp(safeValue(value), 0, 1);
  return `
    <div class="stat-row">
      <span>${label}</span>
      <div class="meter"><div class="meter-fill" style="width:${(clamped * 100).toFixed(0)}%;background:${color}"></div></div>
      <span>${clamped.toFixed(2)}</span>
    </div>
  `;
}

function renderAgentCard(agent) {
  const card = document.querySelector("#agent-card");
  if (!agent) {
    card.innerHTML = `<div class="hint">No agent selected.</div>`;
    return;
  }
  card.innerHTML = `
    <div class="agent-title">
      <div class="agent-name">${agent.label}</div>
      <div class="agent-state">${agent.state}</div>
    </div>
    <div class="status-line"><span>Target</span><strong>${agent.target_kind || "none"}</strong></div>
    <div class="status-line"><span>Last action</span><strong>${agent.last_action}</strong></div>
    <div class="status-line"><span>Position</span><strong>(${agent.x}, ${agent.y})</strong></div>
    <div class="stat-list">
      ${meterRow("Health", agent.health, "#f28f8f")}
      ${meterRow("Hunger", agent.hunger, "#9df584")}
      ${meterRow("Thirst", agent.thirst, "#76d0ff")}
    </div>
  `;
}

function updateMetricCards(frame) {
  const metrics = frame.metrics || {};
  document.querySelector("#metric-tick").textContent = `${frame.tick}`;
  document.querySelector("#metric-population").textContent = `${safeValue(metrics.population)}`;
  document.querySelector("#metric-hunger").textContent = safeValue(metrics.avg_hunger).toFixed(2);
  document.querySelector("#metric-thirst").textContent = safeValue(metrics.avg_thirst).toFixed(2);
}

function setStatusFromArtifact(artifact) {
  const metadata = artifact.metadata || {};
  document.querySelector("#viewer-mode").textContent = metadata.viewer_kind || "replay";
  document.querySelector("#engine-version").textContent = metadata.engine_version || "unknown";
  document.querySelector("#seed-value").textContent = metadata.seed ?? "-";
}

function updateTimeline() {
  timelineInput.max = Math.max(0, state.frames.length - 1);
  timelineInput.value = String(state.frameIndex);
  timelineLabel.textContent = `${state.frameIndex} / ${Math.max(0, state.frames.length - 1)}`;
}

function resolveSelectedAgent(frame) {
  if (!frame?.agents?.length) {
    return null;
  }
  if (!state.selectedAgentId) {
    state.selectedAgentId = frame.selected_agent?.id || frame.agents[0].id;
  }
  const selected = frame.agents.find((agent) => agent.id === state.selectedAgentId);
  return selected || frame.agents[0];
}

function worldLayout(frame) {
  const width = frame.grid.width;
  const height = frame.grid.height;
  const padding = 52;
  const usableWidth = Math.max(260, stageElement.clientWidth - padding * 2);
  const usableHeight = Math.max(260, stageElement.clientHeight - padding * 2);
  const tileSize = Math.floor(Math.min(usableWidth / width, usableHeight / height));
  const offsetX = Math.round((stageElement.clientWidth - tileSize * width) / 2);
  const offsetY = Math.round((stageElement.clientHeight - tileSize * height) / 2);
  return { tileSize, offsetX, offsetY };
}

function toScreenPoint(layout, x, y) {
  return {
    x: layout.offsetX + x * layout.tileSize + layout.tileSize / 2,
    y: layout.offsetY + y * layout.tileSize + layout.tileSize / 2,
  };
}

function drawGrid(frame) {
  gridLayer.removeChildren();
  const layout = worldLayout(frame);
  const grid = new PIXI.Graphics();
  grid.roundRect(
    layout.offsetX - 12,
    layout.offsetY - 12,
    frame.grid.width * layout.tileSize + 24,
    frame.grid.height * layout.tileSize + 24,
    24
  );
  grid.fill({ color: 0x081521, alpha: 0.88 });
  grid.stroke({ color: 0x27445e, width: 2, alpha: 0.7 });

  for (let x = 0; x <= frame.grid.width; x += 1) {
    const px = layout.offsetX + x * layout.tileSize;
    grid.moveTo(px, layout.offsetY);
    grid.lineTo(px, layout.offsetY + frame.grid.height * layout.tileSize);
  }
  for (let y = 0; y <= frame.grid.height; y += 1) {
    const py = layout.offsetY + y * layout.tileSize;
    grid.moveTo(layout.offsetX, py);
    grid.lineTo(layout.offsetX + frame.grid.width * layout.tileSize, py);
  }
  grid.stroke({ color: 0x173145, width: 1, alpha: 0.72 });
  gridLayer.addChild(grid);
  return layout;
}

function syncNodes(frame, layout) {
  const activeIds = new Set();
  for (const node of frame.nodes) {
    activeIds.add(node.id);
    let container = state.nodeSprites.get(node.id);
    if (!container) {
      const glow = new PIXI.Graphics();
      const body = new PIXI.Graphics();
      const label = new PIXI.Text({
        text: node.label,
        style: {
          fill: "#dce8f6",
          fontFamily: "IBM Plex Sans",
          fontSize: 12,
          fontWeight: "600",
        },
      });
      label.anchor.set(0.5, 0);
      container = new PIXI.Container();
      container.addChild(glow, body, label);
      state.nodeSprites.set(node.id, container);
      nodeLayer.addChild(container);
    }

    const [glow, body, label] = container.children;
    const point = toScreenPoint(layout, node.x, node.y);
    const color = PIXI.Color.shared.setValue(node.color).toNumber();
    glow.clear();
    glow.circle(0, 0, layout.tileSize * 0.48);
    glow.fill({ color, alpha: 0.14 });
    body.clear();
    body.roundRect(-layout.tileSize * 0.28, -layout.tileSize * 0.28, layout.tileSize * 0.56, layout.tileSize * 0.56, 8);
    body.fill({ color, alpha: 0.92 });
    body.stroke({ color: 0xeaf3ff, width: 2, alpha: 0.16 });
    label.text = `${node.label} ${Math.round(node.stock_ratio * 100)}%`;
    label.y = layout.tileSize * 0.42;
    container.position.set(point.x, point.y);
  }

  for (const [nodeId, container] of state.nodeSprites.entries()) {
    if (!activeIds.has(nodeId)) {
      container.destroy({ children: true });
      state.nodeSprites.delete(nodeId);
    }
  }
}

function drawTrails(frame, previousFrame, layout) {
  trailLayer.removeChildren();
  if (!previousFrame) {
    return;
  }
  const previousById = new Map(previousFrame.agents.map((agent) => [agent.id, agent]));
  const trail = new PIXI.Graphics();
  for (const agent of frame.agents) {
    const previous = previousById.get(agent.id);
    if (!previous) {
      continue;
    }
    const start = toScreenPoint(layout, previous.x, previous.y);
    const end = toScreenPoint(layout, agent.x, agent.y);
    trail.moveTo(start.x, start.y);
    trail.lineTo(end.x, end.y);
  }
  trail.stroke({ color: 0x9ec5ff, width: 2, alpha: 0.18 });
  trailLayer.addChild(trail);
}

function syncAgents(frame, previousFrame, layout) {
  const previousById = new Map((previousFrame?.agents || []).map((agent) => [agent.id, agent]));
  const activeIds = new Set();

  for (const agent of frame.agents) {
    activeIds.add(agent.id);
    let container = state.sprites.get(agent.id);
    if (!container) {
      const halo = new PIXI.Graphics();
      const body = new PIXI.Graphics();
      const label = new PIXI.Text({
        text: agent.label,
        style: {
          fill: "#dce8f6",
          fontFamily: "IBM Plex Sans",
          fontSize: 11,
          fontWeight: "600",
        },
      });
      label.anchor.set(0.5, 1.2);
      container = new PIXI.Container();
      container.eventMode = "static";
      container.cursor = "pointer";
      container.on("pointertap", () => {
        state.selectedAgentId = agent.id;
        renderFrame(state.frameIndex);
      });
      container.addChild(halo, body, label);
      state.sprites.set(agent.id, container);
      agentLayer.addChild(container);
    }

    const [halo, body, label] = container.children;
    const selected = agent.id === state.selectedAgentId;
    const color = selected ? 0xf5b156 : 0xf6f8fb;
    const point = toScreenPoint(layout, agent.x, agent.y);
    const previous = previousById.get(agent.id);
    const origin = previous ? toScreenPoint(layout, previous.x, previous.y) : point;
    const interpolation = state.playing ? clamp(state.accumulatorMs / state.tickDurationMs, 0, 1) : 1;
    const drawX = origin.x + (point.x - origin.x) * interpolation;
    const drawY = origin.y + (point.y - origin.y) * interpolation;

    halo.clear();
    halo.circle(0, 0, layout.tileSize * 0.28);
    halo.fill({ color, alpha: selected ? 0.22 : 0.0 });

    body.clear();
    body.circle(0, 0, layout.tileSize * 0.16);
    body.fill({ color, alpha: agent.health > 0 ? 1.0 : 0.35 });
    body.stroke({ color: 0x152433, width: 2, alpha: 0.7 });

    label.text = agent.label;
    label.alpha = selected ? 1.0 : 0.66;
    container.position.set(drawX, drawY);
  }

  for (const [agentId, container] of state.sprites.entries()) {
    if (!activeIds.has(agentId)) {
      container.destroy({ children: true });
      state.sprites.delete(agentId);
    }
  }
}

function renderFrame(frameIndex) {
  if (!state.frames.length) {
    return;
  }
  state.frameIndex = clamp(frameIndex, 0, state.frames.length - 1);
  const frame = state.frames[state.frameIndex];
  const previousFrame = state.frameIndex > 0 ? state.frames[state.frameIndex - 1] : null;
  const selected = resolveSelectedAgent(frame);
  const layout = drawGrid(frame);
  drawTrails(frame, previousFrame, layout);
  syncNodes(frame, layout);
  syncAgents(frame, previousFrame, layout);
  updateMetricCards(frame);
  renderAgentCard(selected);
  updateTimeline();
}

function setArtifact(artifact) {
  state.artifact = artifact;
  state.frames = artifact.snapshots || [];
  state.frameIndex = 0;
  state.accumulatorMs = 0;
  state.tickDurationMs = artifact.metadata?.tick_duration_ms || TICK_MS_FALLBACK;
  state.selectedAgentId = artifact.final_state?.selected_agent?.id || artifact.snapshots?.[0]?.selected_agent?.id || null;
  setStatusFromArtifact(artifact);
  renderFrame(0);
}

async function loadArtifactFromUrl(path) {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`Failed to load artifact from ${path}`);
  }
  return response.json();
}

async function loadArtifactFromFile(file) {
  const text = await file.text();
  return JSON.parse(text);
}

function setPlaying(nextValue) {
  state.playing = nextValue;
  playToggle.textContent = state.playing ? "Pause" : "Play";
}

playToggle.addEventListener("click", () => {
  setPlaying(!state.playing);
});

stepButton.addEventListener("click", () => {
  setPlaying(false);
  renderFrame(state.frameIndex + 1);
});

resetButton.addEventListener("click", () => {
  state.accumulatorMs = 0;
  renderFrame(0);
});

timelineInput.addEventListener("input", (event) => {
  setPlaying(false);
  renderFrame(Number(event.target.value));
});

artifactInput.addEventListener("change", async (event) => {
  const [file] = event.target.files || [];
  if (!file) {
    return;
  }
  const artifact = await loadArtifactFromFile(file);
  setArtifact(artifact);
});

pixiApp.ticker.add(() => {
  if (!state.playing || state.frames.length <= 1) {
    return;
  }
  state.accumulatorMs += pixiApp.ticker.deltaMS;
  if (state.accumulatorMs >= state.tickDurationMs) {
    state.accumulatorMs = 0;
    if (state.frameIndex >= state.frames.length - 1) {
      setPlaying(false);
      return;
    }
    renderFrame(state.frameIndex + 1);
  } else {
    renderFrame(state.frameIndex);
  }
});

window.render_game_to_text = () => {
  const frame = state.frames[state.frameIndex];
  const selected = resolveSelectedAgent(frame);
  return JSON.stringify({
    mode: state.artifact?.metadata?.mode || "unloaded",
    tick: frame?.tick ?? 0,
    frame_index: state.frameIndex,
    total_frames: state.frames.length,
    selected_agent: selected
      ? {
          id: selected.id,
          label: selected.label,
          x: selected.x,
          y: selected.y,
          health: selected.health,
          hunger: selected.hunger,
          thirst: selected.thirst,
          state: selected.state,
          target_kind: selected.target_kind,
        }
      : null,
    metrics: frame?.metrics || null,
    coordinate_system: {
      origin: "top-left",
      x_direction: "right",
      y_direction: "down",
    },
  });
};

window.advanceTime = (ms) => {
  if (!state.frames.length) {
    return;
  }
  const steps = Math.max(1, Math.round(ms / state.tickDurationMs));
  renderFrame(Math.min(state.frameIndex + steps, state.frames.length - 1));
};

window.addEventListener("resize", () => {
  renderFrame(state.frameIndex);
});

try {
  const artifact = await loadArtifactFromUrl(artifactPath);
  setArtifact(artifact);
} catch (error) {
  setPlaying(false);
  document.querySelector("#viewer-mode").textContent = "awaiting artifact";
  document.querySelector("#agent-card").innerHTML = `
    <div class="hint">
      No default replay was found. Export one from Python and load it here.
      <br /><br />
      Example:
      <br />
      <code>python main.py --mode spatial_v1_prototype --days 120 --households 1 --members 6 --artifact --out viewer/public/demo-spatial.json</code>
    </div>
  `;
  console.warn(error);
}
