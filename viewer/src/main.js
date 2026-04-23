import "./style.css";
import * as PIXI from "pixi.js";

const DEFAULT_ARTIFACT_PATH = "/demo-spatial.json";
const DEFAULT_LIVE_URL = "http://127.0.0.1:8765";
const TICK_MS_FALLBACK = 280;

const state = {
  artifact: null,
  frames: [],
  frameIndex: 0,
  playing: false,
  tickDurationMs: TICK_MS_FALLBACK,
  selectedAgentId: null,
  accumulatorMs: 0,
  transition: null,
  sprites: new Map(),
  nodeSprites: new Map(),
  source: "unloaded",
  liveUrl: new URLSearchParams(window.location.search).get("live") || DEFAULT_LIVE_URL,
  liveRequestInFlight: false,
};

const appRoot = document.querySelector("#app");
appRoot.innerHTML = `
  <div class="shell">
    <main class="workspace">
      <section class="brandline">
        <div class="brand-copy">
          <div class="micro-tag">GAIA Spatial Prototype</div>
          <h1>First visible world</h1>
          <p>Python remains authoritative. The viewer can replay saved artifacts or step a live spatial session directly so movement can be inspected while rules change.</p>
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
        <button class="btn" id="play-toggle">Play</button>
        <button class="btn" id="step-btn">Step</button>
        <button class="btn" id="reset-btn">Reset</button>
        <button class="btn" id="connect-live-btn">Connect live</button>
        <button class="btn" id="load-demo-btn">Load demo</button>
        <label class="file-label">
          Load artifact
          <input id="artifact-input" type="file" accept="application/json" />
        </label>
        <div class="timeline-wrap">
          <input id="timeline" type="range" min="0" max="0" step="1" value="0" />
          <span id="timeline-label">0 / 0</span>
        </div>
      </section>
    </main>

    <aside class="sidebar">
      <section class="panel">
        <h2>Run Status</h2>
        <div class="status-line"><span>Source</span><strong id="source-mode">unloaded</strong></div>
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
        <div class="hint" id="usage-copy">
          Connect to the Python live service for true step-by-step inspection, or fall back to a saved artifact replay.
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
const connectLiveButton = document.querySelector("#connect-live-btn");
const loadDemoButton = document.querySelector("#load-demo-btn");

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

function updateStatus(metadata = {}) {
  document.querySelector("#source-mode").textContent = state.source;
  document.querySelector("#viewer-mode").textContent = metadata.viewer_kind || metadata.service_kind || "replay";
  document.querySelector("#engine-version").textContent = metadata.engine_version || "unknown";
  document.querySelector("#seed-value").textContent = metadata.seed ?? "-";
}

function updateUsageCopy(message) {
  document.querySelector("#usage-copy").textContent = message;
}

function clearTransition() {
  state.accumulatorMs = 0;
  state.transition = null;
}

function startTransition(fromFrame, toFrame, displayIndex) {
  state.accumulatorMs = 0;
  state.transition = {
    fromFrame,
    toFrame,
    displayIndex,
  };
}

function transitionProgress() {
  if (!state.transition) {
    return 1;
  }
  return clamp(state.accumulatorMs / state.tickDurationMs, 0, 1);
}

function updateTimeline(displayIndex = state.frameIndex) {
  timelineInput.max = Math.max(0, state.frames.length - 1);
  timelineInput.value = String(displayIndex);
  timelineLabel.textContent = `${displayIndex} / ${Math.max(0, state.frames.length - 1)}`;
  timelineInput.disabled = state.source === "live" && state.playing;
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

function syncAgents(frame, previousFrame, layout, interpolation = 1) {
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
        renderCurrentView();
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

function renderScene(frame, previousFrame = null, interpolation = 1, displayIndex = state.frameIndex) {
  const selected = resolveSelectedAgent(frame);
  const layout = drawGrid(frame);
  drawTrails(frame, previousFrame, layout);
  syncNodes(frame, layout);
  syncAgents(frame, previousFrame, layout, interpolation);
  updateMetricCards(frame);
  renderAgentCard(selected);
  updateTimeline(displayIndex);
}

function renderCurrentView() {
  if (!state.frames.length) {
    return;
  }
  if (state.transition) {
    renderScene(
      state.transition.toFrame,
      state.transition.fromFrame,
      transitionProgress(),
      state.transition.displayIndex
    );
    return;
  }
  const frame = state.frames[state.frameIndex];
  const previousFrame = state.frameIndex > 0 ? state.frames[state.frameIndex - 1] : null;
  renderScene(frame, previousFrame, 1, state.frameIndex);
}

function renderFrame(frameIndex) {
  if (!state.frames.length) {
    return;
  }
  clearTransition();
  state.frameIndex = clamp(frameIndex, 0, state.frames.length - 1);
  renderCurrentView();
}

function setSource(nextSource) {
  state.source = nextSource;
  document.querySelector("#source-mode").textContent = nextSource;
}

function setArtifact(artifact, options = {}) {
  state.artifact = artifact;
  state.frames = artifact.snapshots || [];
  state.frameIndex = 0;
  clearTransition();
  state.tickDurationMs = artifact.metadata?.tick_duration_ms || TICK_MS_FALLBACK;
  state.selectedAgentId = artifact.final_state?.selected_agent?.id || artifact.snapshots?.[0]?.selected_agent?.id || null;
  setSource(options.source || "replay");
  updateStatus(artifact.metadata);
  updateUsageCopy("Replay mode draws saved snapshots. Load another artifact or connect to the live Python service when you want live stepping.");
  renderCurrentView();
}

function upsertFrame(frame) {
  const lastFrame = state.frames[state.frames.length - 1];
  if (!lastFrame || frame.tick > lastFrame.tick) {
    state.frames.push(frame);
    return;
  }
  if (frame.tick === lastFrame.tick) {
    state.frames[state.frames.length - 1] = frame;
    return;
  }
  const index = state.frames.findIndex((item) => item.tick === frame.tick);
  if (index >= 0) {
    state.frames[index] = frame;
  } else {
    state.frames.push(frame);
    state.frames.sort((left, right) => left.tick - right.tick);
  }
}

function ingestLiveState(payload, options = {}) {
  const metadata = payload.metadata || {};
  const frame = payload.snapshot;
  if (!frame) {
    return;
  }
  const previousFrame = state.frames[state.frames.length - 1] || null;
  let nextFrameIndex = state.frameIndex;
  if (options.resetHistory) {
    state.frames = [frame];
    nextFrameIndex = 0;
    clearTransition();
  } else {
    upsertFrame(frame);
    nextFrameIndex = state.frames.findIndex((item) => item.tick === frame.tick);
    if (nextFrameIndex < 0) {
      nextFrameIndex = state.frames.length - 1;
    }
    if (state.playing && previousFrame && frame.tick > previousFrame.tick) {
      startTransition(previousFrame, frame, nextFrameIndex);
    } else {
      clearTransition();
    }
  }
  state.artifact = {
    metadata,
    snapshots: state.frames,
    final_state: frame,
  };
  state.tickDurationMs = metadata.tick_duration_ms || TICK_MS_FALLBACK;
  state.selectedAgentId = state.selectedAgentId || frame.selected_agent?.id || frame.agents?.[0]?.id || null;
  setSource("live");
  updateStatus(metadata);
  updateUsageCopy("Live mode steps the Python service directly. Play requests new ticks from the backend; reset restarts the live world.");
  if (!state.transition) {
    state.frameIndex = nextFrameIndex;
  }
  renderCurrentView();
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

async function fetchLive(path, options = {}) {
  const response = await fetch(`${state.liveUrl}${path}`, {
    headers: {
      "Content-Type": "application/json",
    },
    ...options,
  });
  if (!response.ok) {
    throw new Error(`Live service request failed: ${response.status} ${response.statusText}`);
  }
  return response.json();
}

async function connectLive(options = {}) {
  const payload = await fetchLive("/state");
  ingestLiveState(payload, { resetHistory: true });
  setPlaying(options.autoPlay === true);
}

async function requestLiveStep(steps = 1) {
  if (state.liveRequestInFlight) {
    return;
  }
  state.liveRequestInFlight = true;
  try {
    const payload = await fetchLive("/step", {
      method: "POST",
      body: JSON.stringify({ steps }),
    });
    ingestLiveState(payload, { resetHistory: false });
  } finally {
    state.liveRequestInFlight = false;
  }
}

async function resetLiveSession() {
  if (state.liveRequestInFlight) {
    return;
  }
  state.liveRequestInFlight = true;
  try {
    const payload = await fetchLive("/reset", {
      method: "POST",
      body: JSON.stringify({}),
    });
    clearTransition();
    state.selectedAgentId = null;
    ingestLiveState(payload, { resetHistory: true });
  } finally {
    state.liveRequestInFlight = false;
  }
}

function setPlaying(nextValue) {
  if (!nextValue && state.transition) {
    state.frameIndex = state.transition.displayIndex;
    clearTransition();
  }
  state.playing = nextValue;
  playToggle.textContent = state.playing ? "Pause" : "Play";
  if (!state.playing) {
    renderCurrentView();
  }
}

playToggle.addEventListener("click", async () => {
  if (state.source === "live" && !state.frames.length) {
    try {
      await connectLive({ autoPlay: true });
      return;
    } catch (error) {
      updateUsageCopy(error.message);
      return;
    }
  }
  setPlaying(!state.playing);
});

stepButton.addEventListener("click", async () => {
  setPlaying(false);
  if (state.source === "live") {
    try {
      await requestLiveStep(1);
    } catch (error) {
      updateUsageCopy(error.message);
    }
    return;
  }
  renderFrame(state.frameIndex + 1);
});

resetButton.addEventListener("click", async () => {
  clearTransition();
  if (state.source === "live") {
    try {
      await resetLiveSession();
    } catch (error) {
      updateUsageCopy(error.message);
    }
    return;
  }
  renderFrame(0);
});

connectLiveButton.addEventListener("click", async () => {
  try {
    await connectLive({ autoPlay: false });
  } catch (error) {
    setPlaying(false);
    updateUsageCopy(`Could not connect to live service at ${state.liveUrl}. Start spatial_live_service.py and try again.`);
  }
});

loadDemoButton.addEventListener("click", async () => {
  try {
    const artifact = await loadArtifactFromUrl(artifactPath);
    setPlaying(false);
    setArtifact(artifact, { source: "replay" });
  } catch (error) {
    updateUsageCopy("No demo artifact was found. Export one from Python or connect to the live service.");
  }
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
  setPlaying(false);
  setArtifact(artifact, { source: "replay" });
});

pixiApp.ticker.add(() => {
  if (!state.frames.length) {
    return;
  }

  if (!state.playing) {
    renderCurrentView();
    return;
  }

  if (state.source === "live") {
    if (state.transition) {
      state.accumulatorMs += pixiApp.ticker.deltaMS;
      renderCurrentView();
      if (transitionProgress() >= 1) {
        state.frameIndex = state.transition.displayIndex;
        clearTransition();
      }
      return;
    }

    renderCurrentView();
    if (!state.liveRequestInFlight) {
      void requestLiveStep(1).catch((error) => {
        setPlaying(false);
        updateUsageCopy(error.message);
      });
    }
    return;
  }

  if (!state.transition) {
    if (state.frameIndex >= state.frames.length - 1) {
      setPlaying(false);
      return;
    }
    startTransition(state.frames[state.frameIndex], state.frames[state.frameIndex + 1], state.frameIndex + 1);
  }

  state.accumulatorMs += pixiApp.ticker.deltaMS;
  renderCurrentView();
  if (transitionProgress() >= 1) {
    state.frameIndex = state.transition.displayIndex;
    clearTransition();
    if (state.frameIndex >= state.frames.length - 1) {
      setPlaying(false);
    }
  }
});

window.render_game_to_text = () => {
  const frame = state.transition?.toFrame || state.frames[state.frameIndex];
  const selected = resolveSelectedAgent(frame);
  return JSON.stringify({
    mode: state.artifact?.metadata?.mode || "unloaded",
    source: state.source,
    tick: frame?.tick ?? 0,
    frame_index: state.transition?.displayIndex ?? state.frameIndex,
    total_frames: state.frames.length,
    transition_progress: state.transition ? transitionProgress() : 1,
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

window.advanceTime = async (ms) => {
  if (!state.frames.length && state.source !== "live") {
    return;
  }
  const steps = Math.max(1, Math.round(ms / state.tickDurationMs));
  if (state.source === "live") {
    await requestLiveStep(steps);
    return;
  }
  renderFrame(Math.min(state.frameIndex + steps, state.frames.length - 1));
};

window.addEventListener("resize", () => {
  renderCurrentView();
});

async function initialize() {
  try {
    await connectLive({ autoPlay: true });
    return;
  } catch (error) {
    setPlaying(false);
  }

  try {
    const artifact = await loadArtifactFromUrl(artifactPath);
    setArtifact(artifact, { source: "replay" });
  } catch (error) {
    setPlaying(false);
    updateStatus({});
    setSource("awaiting-data");
    updateUsageCopy(`No live service was found at ${state.liveUrl} and no replay artifact was available. Start spatial_live_service.py or export demo-spatial.json.`);
    document.querySelector("#agent-card").innerHTML = `
      <div class="hint">
        Start the live service:
        <br /><br />
        <code>python spatial_live_service.py --port 8765</code>
        <br /><br />
        Or export a replay:
        <br /><br />
        <code>python main.py --mode spatial_v1_prototype --days 120 --households 1 --members 6 --artifact --out viewer/public/demo-spatial.json</code>
      </div>
    `;
  }
}

await initialize();
