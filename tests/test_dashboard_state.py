"""Tests for the live dashboard state layer."""

from __future__ import annotations

import json

import pytest

from atdss.config import load_config
from atdss.dashboard.state import LiveSimulation


@pytest.fixture(scope="module")
def config():
    return load_config()


@pytest.fixture()
def simulation(config):
    return LiveSimulation(
        config,
        strategy="fcfs",
        flights=30,
        seed=3,
        rate=30.0,
        speed=60.0,
    )


def flight_by_id(snapshot, aircraft_id):
    return next(item for item in snapshot["flights"] if item["id"] == aircraft_id)


def test_snapshot_is_complete_and_json_serializable(simulation):
    snapshot = simulation.snapshot()

    assert snapshot["airport"]["icao"] == "VOCI"
    assert snapshot["airport"]["iata"] == "COK"
    assert snapshot["airport"]["runway"] == "09"
    assert snapshot["airport"]["map"]["runway"]["id"] == "09"
    assert snapshot["airport"]["map"]["approach"]["distance_nm"] == pytest.approx(10.0)
    assert len(snapshot["flights"]) == 30
    assert snapshot["metrics"]["total_flights"] == 30
    assert snapshot["scenario"]["strategy"] == "fcfs"
    assert snapshot["final_approach"]["faf_distance_nm"] == pytest.approx(10.0)
    assert snapshot["sim_time_text"] == "00:00:00"
    assert snapshot["flights"][0]["callsign"]
    assert snapshot["flights"][0]["origin"]
    assert snapshot["flights"][0]["origin_name"]
    assert snapshot["flights"][0]["origin_lat"] is not None
    assert snapshot["flights"][0]["wake"] in {"H", "M", "L"}
    json.dumps(snapshot)


def test_flight_status_transitions(config):
    simulation = LiveSimulation(config, flights=100, seed=7, rate=30.0, speed=60.0)
    target = simulation.aircraft[-1]

    simulation.sim_time = max(0.0, target.scheduled_arrival_sec - 2000.0)
    assert flight_by_id(simulation.snapshot(), target.id)["status"] == "scheduled"

    simulation.sim_time = target.scheduled_arrival_sec - 1200.0
    assert flight_by_id(simulation.snapshot(), target.id)["status"] == "en_route"

    simulation.sim_time = (
        target.actual_landing_sec - simulation.final_approach_duration - 10.0
    )
    holding = flight_by_id(simulation.snapshot(), target.id)
    assert holding["status"] == "holding"
    assert holding["on_final"] is False
    assert holding["position_nm"] is None

    simulation.sim_time = (
        target.actual_landing_sec - simulation.final_approach_duration + 10.0
    )
    final = flight_by_id(simulation.snapshot(), target.id)
    assert final["status"] == "final"
    assert final["on_final"] is True
    assert final["position_nm"] is not None
    assert 0.0 < final["position_nm"] <= simulation.config.faf_distance_nm

    simulation.sim_time = target.actual_landing_sec + 1.0
    landed = flight_by_id(simulation.snapshot(), target.id)
    assert landed["status"] == "landed"
    assert landed["position_nm"] == 0.0


def test_runway_occupancy_is_reported(simulation):
    aircraft = simulation.aircraft[0]
    simulation.sim_time = aircraft.actual_landing_sec + 1.0
    snapshot = simulation.snapshot()

    assert snapshot["runway"]["status"] == "occupied"
    assert snapshot["runway"]["current_flight"] == aircraft.callsign
    assert snapshot["runway"]["next_flight"] is not None


def test_pause_speed_seek_and_reset(simulation):
    simulation.pause()
    assert simulation.paused is True
    start = simulation.sim_time
    simulation.tick()
    assert simulation.sim_time == pytest.approx(start)

    simulation.resume()
    assert simulation.paused is False

    simulation.set_speed(120.0)
    assert simulation.speed == pytest.approx(120.0)
    with pytest.raises(ValueError):
        simulation.set_speed(0)

    simulation.seek(0.5)
    assert simulation.paused is True
    assert simulation.sim_time == pytest.approx(
        simulation.start_time + 0.5 * (simulation.end_time - simulation.start_time)
    )

    simulation.reset()
    assert simulation.sim_time == pytest.approx(0.0)
    assert simulation.paused is False
    assert len(simulation.snapshot()["flights"]) == 30


def test_regenerate_changes_scenario(simulation):
    simulation.regenerate(flights=12, seed=99, strategy="priority", rate=24.0)
    snapshot = simulation.snapshot()

    assert len(snapshot["flights"]) == 12
    assert snapshot["scenario"]["seed"] == 99
    assert snapshot["scenario"]["strategy"] == "priority"
    assert snapshot["scenario"]["rate"] == pytest.approx(24.0)
    assert simulation.sim_time == pytest.approx(0.0)


def test_advance_rejects_negative_time(simulation):
    with pytest.raises(ValueError):
        simulation.advance(-1.0)

    simulation.advance(10.0)
    assert simulation.sim_time == pytest.approx(10.0)


def test_invalid_regeneration_keeps_previous_scenario(simulation):
    before = simulation.snapshot()

    with pytest.raises(ValueError):
        simulation.regenerate(flights=0)
    with pytest.raises(ValueError):
        simulation.regenerate(rate=-1)
    with pytest.raises(ValueError):
        simulation.regenerate(strategy="unknown")

    after = simulation.snapshot()
    assert after["scenario"]["flights"] == before["scenario"]["flights"]
    assert after["scenario"]["seed"] == before["scenario"]["seed"]
    assert after["scenario"]["strategy"] == before["scenario"]["strategy"]
    assert after["scenario"]["rate"] == before["scenario"]["rate"]
