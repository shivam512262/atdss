"""Core data models for the AT-DSS simulation milestone."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .config import WakeCategory


class Strategy(str, Enum):
    """Baseline sequencing strategies available in this milestone."""

    FCFS = "fcfs"
    PRIORITY = "priority"


@dataclass
class Aircraft:
    """A single arrival with scheduled, assigned, and actual landing times."""

    id: str
    icao_type: str
    wake: WakeCategory
    scheduled_arrival_sec: float
    callsign: str = ""
    flight_number: str = ""
    origin: str = ""
    runway: str = "24"
    assigned_landing_sec: float | None = None
    actual_landing_sec: float | None = None
    sequence_position: int = -1
    delay_sec: float = 0.0
    fuel_proxy_kg: float = 0.0

    @property
    def assigned_or_scheduled_sec(self) -> float:
        return (
            self.assigned_landing_sec
            if self.assigned_landing_sec is not None
            else self.scheduled_arrival_sec
        )

    def reset_schedule(self) -> None:
        """Clear sequencing and simulation state before evaluating a new strategy."""
        self.assigned_landing_sec = None
        self.actual_landing_sec = None
        self.sequence_position = -1
        self.delay_sec = 0.0
        self.fuel_proxy_kg = 0.0


@dataclass(frozen=True)
class ConflictRisk:
    """Consecutive-pair separation analysis result.

    ``violation`` is the hard safety check (actual gap below required separation).
    ``conflict_risk`` measures whether the unsequenced schedule was already below
    the required gap and therefore needed intervention.
    ``tight`` flags a small post-sequencing margin.
    """

    leading_id: str
    following_id: str
    leading_wake: WakeCategory
    following_wake: WakeCategory
    required_sep_sec: float
    scheduled_gap_sec: float
    actual_gap_sec: float
    margin_sec: float
    conflict_risk: bool
    tight: bool
    violation: bool


@dataclass
class SimulationResult:
    """Output of one sequencing strategy on one traffic sample."""

    strategy: str
    sequence: list[Aircraft]
    conflicts: list[ConflictRisk] = field(default_factory=list)
    start_time_sec: float = 0.0
    end_time_sec: float = 0.0
    metrics: dict[str, float | str] = field(default_factory=dict)
