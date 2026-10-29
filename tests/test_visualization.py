"""Tests for the standalone HTML animation."""

from __future__ import annotations

import json

import pytest

from atdss.config import load_config
from atdss.experiments import run_single
from atdss.visualization import (
    build_visual_payload,
    render_html,
    write_visualization,
)


@pytest.fixture(scope="module")
def config():
    return load_config()


@pytest.fixture(scope="module")
def result(config):
    return run_single(
        config,
        strategy="fcfs",
        flights=12,
        seed=21,
        arrival_rate_per_hour=30,
    )


def test_payload_contains_aircraft_and_runway(result, config):
    payload = build_visual_payload(config, result)
    assert len(payload["aircraft"]) == 12
    assert payload["airport"]["icao"] == "VOCI"
    assert payload["runway"]["id"] == "09"
    assert payload["runway"]["faf_distance_nm"] == pytest.approx(10.0)
    assert payload["runway"]["final_approach_duration_sec"] == pytest.approx(
        10.0 / (140.0 / 3600.0)
    )
    assert payload["animation_end_sec"] > payload["animation_start_sec"]
    assert payload["aircraft"][0]["actual"] >= payload["aircraft"][0]["scheduled"]
    json.dumps(payload)  # Must be JSON-serializable for embedding.


def test_render_html_is_self_contained(result, config):
    payload = build_visual_payload(config, result)
    output = render_html(payload, title="Test animation")
    callsign = payload["aircraft"][0]["callsign"]

    assert output.startswith("<!DOCTYPE html>")
    assert "<title>Test animation</title>" in output
    assert "const DATA = {" in output
    assert "requestAnimationFrame" in output
    assert callsign in output
    assert "__DATA_JSON__" not in output
    assert "__PAGE_TITLE__" not in output


def test_write_visualization_creates_file(result, config, tmp_path):
    path = write_visualization(config, result, tmp_path / "simulation.html")
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "AT-DSS Arrival Simulation" in text
    assert str(tmp_path) not in text  # no accidental local path leak
