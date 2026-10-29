"""Tests for the FastAPI dashboard surface."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from atdss.config import load_config
from atdss.dashboard.app import create_app


@pytest.fixture()
def client():
    app = create_app(
        load_config(),
        flights=12,
        seed=5,
        strategy="fcfs",
        rate=30.0,
        speed=60.0,
        start_ticker=False,
    )
    with TestClient(app) as test_client:
        yield test_client


def test_index_and_static_assets(client):
    index = client.get("/")
    assert index.status_code == 200
    assert "AT-DSS Live Arrival Simulator" in index.text
    assert 'id="map"' in index.text
    assert 'id="speedButtons"' in index.text
    assert "Normal 1×" in index.text
    assert "Live airport map" in index.text

    script = client.get("/static/app.js")
    assert script.status_code == 200
    assert "WebSocket" in script.text
    assert "drawMap" in script.text

    styles = client.get("/static/styles.css")
    assert styles.status_code == 200
    assert ":root" in styles.text


def test_health_and_state_endpoints(client):
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["flights"] == 12

    state = client.get("/api/state")
    assert state.status_code == 200
    payload = state.json()
    assert payload["airport"]["icao"] == "VOCI"
    assert payload["airport"]["iata"] == "COK"
    assert payload["airport"]["map"]["runway"]["id"] == "09"
    assert len(payload["flights"]) == 12
    assert "metrics" in payload
    assert "runway" in payload
    assert "alerts" in payload

    flights = client.get("/api/flights")
    assert flights.status_code == 200
    assert len(flights.json()) == 12

    metrics = client.get("/api/metrics")
    assert metrics.status_code == 200
    assert metrics.json()["total_flights"] == 12


def test_control_actions(client):
    paused = client.post("/api/control", json={"action": "pause"})
    assert paused.status_code == 200
    assert paused.json()["paused"] is True

    resumed = client.post("/api/control", json={"action": "resume"})
    assert resumed.status_code == 200
    assert resumed.json()["paused"] is False

    fast = client.post("/api/control", json={"action": "speed", "value": 120})
    assert fast.status_code == 200
    assert fast.json()["speed"] == pytest.approx(120.0)

    reset = client.post("/api/control", json={"action": "reset"})
    assert reset.status_code == 200
    assert reset.json()["sim_time"] == pytest.approx(0.0)

    bad = client.post("/api/control", json={"action": "explode"})
    assert bad.status_code == 400


def test_scenario_regeneration(client):
    response = client.post(
        "/api/scenario",
        json={"flights": 18, "seed": 77, "strategy": "priority", "rate": 24, "speed": 30},
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["flights"]) == 18
    assert payload["scenario"]["seed"] == 77
    assert payload["scenario"]["strategy"] == "priority"
    assert payload["scenario"]["rate"] == pytest.approx(24.0)
    assert payload["speed"] == pytest.approx(30.0)

    invalid = client.post(
        "/api/scenario",
        json={"flights": 0, "seed": 1, "strategy": "fcfs", "rate": 30},
    )
    assert invalid.status_code == 422


def test_websocket_streams_snapshot(client):
    with client.websocket_connect("/ws") as websocket:
        payload = websocket.receive_json()
    assert payload["airport"]["icao"] == "VOCI"
    assert payload["airport"]["runway"] == "09"
    assert len(payload["flights"]) >= 12
