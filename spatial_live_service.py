from __future__ import annotations

import argparse
import json
from dataclasses import replace
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import RLock
from typing import Any
from urllib.parse import urlparse

from gaia_config import SPATIAL_MODE, SimulationConfig
from spatial_simulation import SpatialPrototypeEngine


class SpatialLiveSession:
    def __init__(self, config: SimulationConfig):
        self._lock = RLock()
        self._config = self._ensure_live_defaults(config)
        self._engine = SpatialPrototypeEngine(self._config)

    @staticmethod
    def _ensure_live_defaults(config: SimulationConfig) -> SimulationConfig:
        resolved = config
        if resolved.mode != SPATIAL_MODE:
            resolved = replace(resolved, mode=SPATIAL_MODE)
        if resolved.snapshot_frequency == 0:
            resolved = replace(resolved, snapshot_frequency=1)
        return resolved

    def reset(self, patch: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            if patch:
                merged = self._config.to_dict()
                merged.update(patch)
                if "assumptions" in patch and isinstance(patch["assumptions"], dict):
                    merged["assumptions"] = patch["assumptions"]
                self._config = self._ensure_live_defaults(SimulationConfig.from_dict(merged))
            self._engine = SpatialPrototypeEngine(self._config)
            return self._build_state_unlocked()

    def step(self, steps: int = 1) -> dict[str, Any]:
        steps = max(1, int(steps))
        with self._lock:
            for _ in range(steps):
                self._engine.step()
            return self._build_state_unlocked()

    def _build_state_unlocked(self) -> dict[str, Any]:
        snapshot = self._engine.snapshot()
        return {
            "metadata": {
                "service_kind": "spatial_live_v1",
                "engine_version": "spatial-v1-prototype",
                "mode": self._config.mode,
                "seed": self._config.seed,
                "config": self._config.to_dict(),
                "tick_duration_ms": 280,
            },
            "snapshot": snapshot,
            "history_length": len(self._engine.snapshots),
        }

    def current_state(self) -> dict[str, Any]:
        with self._lock:
            return self._build_state_unlocked()

    def artifact(self) -> dict[str, Any]:
        with self._lock:
            return self._engine.build_artifact().to_dict()


class SpatialLiveRequestHandler(BaseHTTPRequestHandler):
    server_version = "SpatialLiveService/0.1"

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/health":
            self._send_json(HTTPStatus.OK, {"ok": True})
            return
        if path == "/state":
            self._send_json(HTTPStatus.OK, self.server.session.current_state())
            return
        if path == "/artifact":
            self._send_json(HTTPStatus.OK, self.server.session.artifact())
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            payload = self._read_json()
        except json.JSONDecodeError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_json", "detail": str(exc)})
            return

        if path == "/reset":
            patch = payload.get("config") if isinstance(payload, dict) else None
            self._send_json(HTTPStatus.OK, self.server.session.reset(patch=patch))
            return
        if path == "/step":
            steps = payload.get("steps", 1) if isinstance(payload, dict) else 1
            self._send_json(HTTPStatus.OK, self.server.session.step(steps=steps))
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return


class SpatialLiveHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], session: SpatialLiveSession):
        super().__init__(server_address, SpatialLiveRequestHandler)
        self.session = session


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Serve live spatial GAIA state for the PixiJS viewer.")
    parser.add_argument("--host", type=str, default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--days", type=int, default=240)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--households", type=int, default=1)
    parser.add_argument("--members", type=int, default=6)
    parser.add_argument("--grid-width", type=int, default=18)
    parser.add_argument("--grid-height", type=int, default=12)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = SimulationConfig(
        days=args.days,
        seed=args.seed,
        num_households=args.households,
        members_per_household=args.members,
        mode=SPATIAL_MODE,
        snapshot_frequency=1,
        grid_width=args.grid_width,
        grid_height=args.grid_height,
    )
    session = SpatialLiveSession(config=config)
    server = SpatialLiveHTTPServer((args.host, args.port), session=session)
    print(f"Serving live GAIA spatial state on http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
