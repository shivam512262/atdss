"""FastAPI application for the live AT-DSS arrival simulator."""

from __future__ import annotations

import asyncio
import contextlib
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..config import AirportConfig, load_config
from .state import LiveSimulation

STATIC_DIR = Path(__file__).resolve().parent / "static"
SNAPSHOT_INTERVAL_SEC = 0.5


class ControlRequest(BaseModel):
    """Control action sent by the dashboard."""

    action: str = Field(..., description="pause, resume, toggle, speed, reset, seek, regenerate")
    value: float | None = None
    flights: int | None = None
    seed: int | None = None
    strategy: str | None = None
    rate: float | None = None


class ScenarioRequest(BaseModel):
    """Parameters for a newly generated scenario."""

    flights: int = Field(100, ge=1, le=1000)
    seed: int = 42
    strategy: str = "fcfs"
    rate: float = Field(30.0, gt=0, le=120)
    speed: float | None = Field(None, ge=1, le=600)


def create_app(
    config: AirportConfig | None = None,
    *,
    flights: int = 100,
    seed: int = 42,
    strategy: str = "fcfs",
    rate: float = 30.0,
    speed: float = 1.0,
    start_ticker: bool = True,
) -> FastAPI:
    """Build the dashboard app around one live simulation state."""
    airport = config or load_config()
    simulation = LiveSimulation(
        airport,
        strategy=strategy,
        flights=flights,
        seed=seed,
        rate=rate,
        speed=speed,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        task: asyncio.Task[None] | None = None
        if start_ticker:
            task = asyncio.create_task(_ticker())
        try:
            yield
        finally:
            if task is not None:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    async def _ticker() -> None:
        while True:
            await asyncio.sleep(SNAPSHOT_INTERVAL_SEC)
            simulation.tick()

    app = FastAPI(
        title="AT-DSS Live Arrival Simulator",
        description="Synthetic live arrival sequencing, runway, and conflict dashboard.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.simulation = simulation
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "airport": simulation.config.icao,
            "flights": simulation.flights,
            "sim_time": round(simulation.sim_time, 3),
            "paused": simulation.paused,
        }

    @app.get("/api/state")
    async def state() -> dict[str, Any]:
        return simulation.snapshot()

    @app.get("/api/flights")
    async def flights() -> list[dict[str, Any]]:
        return simulation.snapshot()["flights"]

    @app.get("/api/metrics")
    async def metrics() -> dict[str, Any]:
        return simulation.snapshot()["metrics"]

    @app.post("/api/control")
    async def control(payload: ControlRequest) -> dict[str, Any]:
        action = payload.action.strip().lower()
        try:
            if action == "pause":
                simulation.pause()
            elif action == "resume":
                simulation.resume()
            elif action == "toggle":
                simulation.toggle_pause()
            elif action == "speed":
                if payload.value is None:
                    raise HTTPException(status_code=400, detail="speed requires a value")
                simulation.set_speed(payload.value)
            elif action == "reset":
                simulation.reset()
            elif action == "seek":
                if payload.value is None:
                    raise HTTPException(status_code=400, detail="seek requires a value")
                simulation.seek(payload.value)
            elif action == "regenerate":
                simulation.regenerate(
                    flights=payload.flights,
                    seed=payload.seed,
                    strategy=payload.strategy,
                    rate=payload.rate,
                )
            else:
                raise HTTPException(status_code=400, detail=f"Unknown action: {payload.action}")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return simulation.snapshot()

    @app.post("/api/scenario")
    async def scenario(payload: ScenarioRequest) -> dict[str, Any]:
        try:
            simulation.regenerate(
                flights=payload.flights,
                seed=payload.seed,
                strategy=payload.strategy,
                rate=payload.rate,
            )
            if payload.speed is not None:
                simulation.set_speed(payload.speed)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return simulation.snapshot()

    @app.websocket("/ws")
    async def websocket(websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            while True:
                await websocket.send_json(simulation.snapshot())
                await asyncio.sleep(SNAPSHOT_INTERVAL_SEC)
        except (WebSocketDisconnect, RuntimeError):
            return

    return app
