#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VIEWER_DIR="$ROOT_DIR/viewer"

HOST="${GAIA_LIVE_HOST:-127.0.0.1}"
SERVICE_PORT="${GAIA_LIVE_PORT:-8765}"
VIEWER_PORT="${GAIA_VIEWER_PORT:-4173}"
DAYS="${GAIA_DAYS:-240}"
HOUSEHOLDS="${GAIA_HOUSEHOLDS:-1}"
MEMBERS="${GAIA_MEMBERS:-6}"
GRID_WIDTH="${GAIA_GRID_WIDTH:-18}"
GRID_HEIGHT="${GAIA_GRID_HEIGHT:-12}"
FORCE_INSTALL=0

usage() {
  cat <<'EOF'
Run the GAIA live spatial prototype with one command.

Usage:
  ./run_spatial_world.sh
  ./run_spatial_world.sh --install

Optional environment overrides:
  GAIA_LIVE_HOST
  GAIA_LIVE_PORT
  GAIA_VIEWER_PORT
  GAIA_DAYS
  GAIA_HOUSEHOLDS
  GAIA_MEMBERS
  GAIA_GRID_WIDTH
  GAIA_GRID_HEIGHT
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install)
      FORCE_INSTALL=1
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ ! -d "$VIEWER_DIR/node_modules" || "$FORCE_INSTALL" -eq 1 ]]; then
  echo "Installing viewer dependencies in $VIEWER_DIR..."
  (
    cd "$VIEWER_DIR"
    npm install
  )
fi

SERVICE_PID=""

cleanup() {
  if [[ -n "$SERVICE_PID" ]] && kill -0 "$SERVICE_PID" >/dev/null 2>&1; then
    kill "$SERVICE_PID" >/dev/null 2>&1 || true
    wait "$SERVICE_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

echo "Starting GAIA live spatial service on http://$HOST:$SERVICE_PORT ..."
python "$ROOT_DIR/spatial_live_service.py" \
  --host "$HOST" \
  --port "$SERVICE_PORT" \
  --days "$DAYS" \
  --households "$HOUSEHOLDS" \
  --members "$MEMBERS" \
  --grid-width "$GRID_WIDTH" \
  --grid-height "$GRID_HEIGHT" &
SERVICE_PID=$!

if command -v curl >/dev/null 2>&1; then
  for _ in $(seq 1 50); do
    if curl -fsS "http://$HOST:$SERVICE_PORT/health" >/dev/null 2>&1; then
      break
    fi
    sleep 0.2
  done
else
  sleep 1
fi

echo "Starting PixiJS viewer on http://$HOST:$VIEWER_PORT ..."
echo "Press Ctrl-C to stop both the viewer and the Python live service."

(
  cd "$VIEWER_DIR"
  npm run dev -- --host "$HOST" --port "$VIEWER_PORT" --strictPort
)
