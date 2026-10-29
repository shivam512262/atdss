"""Baseline arrival-sequencing strategies and separation enforcement."""

from __future__ import annotations

from .config import AirportConfig
from .models import Aircraft, Strategy

_WAKE_BONUS_SEC = {"H": 180.0, "M": 60.0, "L": 0.0}


def fcfs_sequence(aircraft: list[Aircraft]) -> list[Aircraft]:
    """First-come, first-served ordering by scheduled arrival time."""
    return sorted(aircraft, key=lambda ac: (ac.scheduled_arrival_sec, ac.id))


def priority_sequence(aircraft: list[Aircraft]) -> list[Aircraft]:
    """Bounded wake-priority ordering.

    Heavy aircraft receive a three-minute scheduling bonus and Medium aircraft
    receive one minute, relative to their scheduled arrival. The bounded bonus
    lets a large aircraft move slightly earlier without allowing an arbitrary
    Heavy-first ordering that would starve the rest of the queue. This is a
    baseline heuristic, not an optimized sequence.
    """
    return sorted(
        aircraft,
        key=lambda ac: (
            ac.scheduled_arrival_sec - _WAKE_BONUS_SEC.get(ac.wake.value, 0.0),
            ac.scheduled_arrival_sec,
            ac.id,
        ),
    )


def sequence_for(strategy: Strategy | str, aircraft: list[Aircraft]) -> list[Aircraft]:
    """Return a new ordered list for the requested baseline strategy."""
    value = strategy.value if isinstance(strategy, Strategy) else str(strategy).lower()
    if value == Strategy.FCFS.value:
        return fcfs_sequence(aircraft)
    if value == Strategy.PRIORITY.value:
        return priority_sequence(aircraft)
    raise ValueError(f"Unknown sequencing strategy: {strategy!r}")


def apply_sequence(
    sequence: list[Aircraft], config: AirportConfig
) -> list[Aircraft]:
    """Assign landing times that enforce wake separation after each leader.

    Each aircraft lands no earlier than its scheduled arrival and no earlier than
    the previous aircraft's assigned landing time plus the required wake
    separation. The resulting schedule is therefore separation-feasible: hard
    separation violations should be zero.
    """
    previous: Aircraft | None = None

    for position, aircraft in enumerate(sequence):
        aircraft.sequence_position = position

        if previous is None:
            assigned = max(0.0, aircraft.scheduled_arrival_sec)
        else:
            separation_sec = config.separation_sec_between(
                previous.wake, aircraft.wake
            )
            previous_assigned = previous.assigned_landing_sec
            if previous_assigned is None:
                raise ValueError("Previous aircraft has no assigned landing time")
            assigned = max(
                aircraft.scheduled_arrival_sec,
                previous_assigned + separation_sec,
            )

        aircraft.assigned_landing_sec = assigned
        aircraft.delay_sec = max(0.0, assigned - aircraft.scheduled_arrival_sec)
        aircraft.fuel_proxy_kg = (
            aircraft.delay_sec * config.fuel_flow_kg_s[aircraft.wake]
        )
        previous = aircraft

    return sequence
