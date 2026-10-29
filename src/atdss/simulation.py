"""Discrete-event execution of an assigned landing sequence using SimPy."""

from __future__ import annotations

import simpy

from .config import AirportConfig
from .models import Aircraft, SimulationResult


def run_sequence_simulation(
    sequence: list[Aircraft],
    config: AirportConfig,
    strategy: str,
) -> SimulationResult:
    """Execute a sequence on a single runway and record actual landing times.

    The sequence and assigned times come from the sequencing layer. SimPy is
    used here to model a single-runway resource, runway occupancy, and event
    ordering. Taxi time is not modelled as runway-blocking and is excluded from
    this milestone.
    """
    if not sequence:
        raise ValueError("Cannot simulate an empty sequence")

    env = simpy.Environment()
    runway = simpy.Resource(env, capacity=1)
    landed: list[Aircraft] = []

    def aircraft_process(aircraft: Aircraft) -> simpy.events.Process:
        wait_sec = max(0.0, aircraft.assigned_or_scheduled_sec - env.now)
        if wait_sec > 0:
            yield env.timeout(wait_sec)

        with runway.request() as request:
            yield request
            aircraft.actual_landing_sec = env.now
            aircraft.delay_sec = max(0.0, env.now - aircraft.scheduled_arrival_sec)
            aircraft.fuel_proxy_kg = (
                aircraft.delay_sec * config.fuel_flow_kg_s[aircraft.wake]
            )
            landed.append(aircraft)
            yield env.timeout(config.runway_occupancy_sec)

    for aircraft in sequence:
        env.process(aircraft_process(aircraft))

    last_assigned = max(aircraft.assigned_or_scheduled_sec for aircraft in sequence)
    horizon = last_assigned + (2.0 * config.runway_occupancy_sec) + 60.0
    env.run(until=horizon)

    start_time = min(aircraft.scheduled_arrival_sec for aircraft in sequence)
    end_time = max(
        (aircraft.actual_landing_sec or aircraft.assigned_or_scheduled_sec)
        for aircraft in sequence
    )

    return SimulationResult(
        strategy=strategy,
        sequence=sequence,
        start_time_sec=start_time,
        end_time_sec=end_time,
    )
