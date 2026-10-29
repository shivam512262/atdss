"""Live simulation state for the AT-DSS dashboard."""

from __future__ import annotations

import math
import time
from enum import Enum
from statistics import fmean
from typing import Any

from ..config import AirportConfig
from ..experiments import run_single
from ..models import Aircraft, SimulationResult, Strategy

HOLDING_LEAD_SEC = 15 * 60.0
EN_ROUTE_LEAD_SEC = 30 * 60.0


class FlightStatus(str, Enum):
    SCHEDULED = "scheduled"
    EN_ROUTE = "en_route"
    HOLDING = "holding"
    FINAL = "final"
    LANDED = "landed"


def format_time(seconds: float) -> str:
    """Format simulated seconds as HH:MM:SS."""
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class LiveSimulation:
    """A controllable live clock over one generated arrival scenario."""

    def __init__(
        self,
        config: AirportConfig,
        strategy: str = "fcfs",
        flights: int = 100,
        seed: int = 42,
        rate: float = 30.0,
        speed: float = 1.0,
    ) -> None:
        self.config = config
        self.strategy = str(strategy).lower()
        self.flights = int(flights)
        self.seed = int(seed)
        self.rate = float(rate)
        self.speed = self._validate_speed(speed)
        self._build()

    @staticmethod
    def _validate_speed(speed: float) -> float:
        value = float(speed)
        if not 1.0 <= value <= 600.0:
            raise ValueError("speed must be between 1 and 600")
        return value

    def _build(self) -> None:
        if self.flights < 1:
            raise ValueError("flights must be at least 1")
        if self.rate <= 0:
            raise ValueError("rate must be positive")

        result: SimulationResult = run_single(
            self.config,
            strategy=self.strategy,
            flights=self.flights,
            seed=self.seed,
            arrival_rate_per_hour=self.rate,
        )
        if not result.sequence:
            raise ValueError("Simulation produced no aircraft")

        self.result = result
        self.aircraft = result.sequence
        actual_times = [self._actual_time(aircraft) for aircraft in self.aircraft]
        self.start_time = 0.0
        self.end_time = max(actual_times) + self.config.runway_occupancy_sec + 120.0
        self.sim_time = self.start_time
        self.paused = False
        self.last_tick = time.monotonic()
        self.final_approach_duration = (
            self.config.faf_distance_nm / self.config.approach_speed_nm_per_sec
        )
        self.runway = self.config.arrival_runway
        self.map_data = self.config.map_data or {}
        self.origin_airports = self.map_data.get("origin_airports", {})
        self._conflict_by_following = {
            conflict.following_id: conflict for conflict in result.conflicts
        }

    def reset(self) -> None:
        """Restart the same scenario from the beginning."""
        self._build()

    def regenerate(
        self,
        flights: int | None = None,
        seed: int | None = None,
        strategy: str | None = None,
        rate: float | None = None,
    ) -> None:
        """Regenerate the scenario with any supplied parameter changes."""
        new_flights = self.flights if flights is None else int(flights)
        new_seed = self.seed if seed is None else int(seed)
        new_strategy = (
            self.strategy if strategy is None else str(strategy).lower()
        )
        new_rate = self.rate if rate is None else float(rate)

        if new_flights < 1:
            raise ValueError("flights must be at least 1")
        if not math.isfinite(new_rate) or new_rate <= 0:
            raise ValueError("rate must be positive")
        if new_strategy not in {item.value for item in Strategy}:
            raise ValueError(f"Unknown sequencing strategy: {new_strategy!r}")

        self.flights = new_flights
        self.seed = new_seed
        self.strategy = new_strategy
        self.rate = new_rate
        self._build()

    def advance(self, seconds: float) -> None:
        """Advance simulated time by a fixed amount (used by tick and tests)."""
        if seconds < 0:
            raise ValueError("seconds must be non-negative")
        self.sim_time = min(self.end_time, self.sim_time + float(seconds))
        if self.sim_time >= self.end_time:
            self.paused = True

    def tick(self) -> dict[str, Any]:
        """Advance according to wall-clock time and return a snapshot."""
        now = time.monotonic()
        elapsed = max(0.0, now - self.last_tick)
        self.last_tick = now
        if not self.paused:
            self.advance(elapsed * self.speed)
        return self.snapshot()

    def pause(self) -> None:
        self.paused = True
        self.last_tick = time.monotonic()

    def resume(self) -> None:
        self.paused = False
        self.last_tick = time.monotonic()

    def toggle_pause(self) -> None:
        if self.paused:
            self.resume()
        else:
            self.pause()

    def set_speed(self, speed: float) -> None:
        self.speed = self._validate_speed(speed)

    def seek(self, fraction: float) -> None:
        """Jump to a fractional position in the scenario and pause."""
        value = max(0.0, min(1.0, float(fraction)))
        self.sim_time = self.start_time + value * (self.end_time - self.start_time)
        self.paused = True
        self.last_tick = time.monotonic()

    @staticmethod
    def _actual_time(aircraft: Aircraft) -> float:
        if aircraft.actual_landing_sec is not None:
            return aircraft.actual_landing_sec
        return aircraft.assigned_or_scheduled_sec

    def _status_for(self, aircraft: Aircraft, t: float) -> FlightStatus:
        actual = self._actual_time(aircraft)
        scheduled = aircraft.scheduled_arrival_sec
        if t >= actual:
            return FlightStatus.LANDED
        if t >= actual - self.final_approach_duration:
            return FlightStatus.FINAL
        if t >= scheduled - HOLDING_LEAD_SEC:
            return FlightStatus.HOLDING
        if t >= scheduled - EN_ROUTE_LEAD_SEC:
            return FlightStatus.EN_ROUTE
        return FlightStatus.SCHEDULED

    def _position_nm(self, aircraft: Aircraft, t: float, status: FlightStatus) -> float | None:
        actual = self._actual_time(aircraft)
        if status == FlightStatus.LANDED:
            return 0.0
        if status == FlightStatus.FINAL:
            distance = (actual - t) * self.config.approach_speed_nm_per_sec
            return max(0.0, min(self.config.faf_distance_nm, distance))
        return None

    def _flight_snapshot(self, aircraft: Aircraft, t: float) -> dict[str, Any]:
        scheduled = aircraft.scheduled_arrival_sec
        assigned = aircraft.assigned_or_scheduled_sec
        actual = self._actual_time(aircraft)
        status = self._status_for(aircraft, t)
        effective = actual if status == FlightStatus.LANDED else assigned
        delay = max(0.0, effective - scheduled)
        position = self._position_nm(aircraft, t, status)
        conflict = self._conflict_by_following.get(aircraft.id)
        origin_info = self.origin_airports.get(aircraft.origin, {})

        return {
            "id": aircraft.id,
            "callsign": aircraft.callsign,
            "flight_number": aircraft.flight_number or aircraft.callsign,
            "type": aircraft.icao_type,
            "wake": aircraft.wake.value,
            "origin": aircraft.origin,
            "origin_name": origin_info.get("name", aircraft.origin),
            "origin_lat": origin_info.get("lat"),
            "origin_lon": origin_info.get("lon"),
            "runway": aircraft.runway,
            "sequence_position": aircraft.sequence_position,
            "scheduled": round(scheduled, 3),
            "assigned": round(assigned, 3),
            "actual": round(actual, 3),
            "eta": round(actual if status == FlightStatus.LANDED else assigned, 3),
            "status": status.value,
            "delay": round(delay, 3),
            "fuel_proxy_kg": round(aircraft.fuel_proxy_kg, 3),
            "position_nm": (
                None if position is None else round(position, 3)
            ),
            "on_final": status == FlightStatus.FINAL,
            "holding": status == FlightStatus.HOLDING,
            "conflict_risk": bool(conflict.conflict_risk) if conflict else False,
            "separation_margin_sec": (
                round(conflict.margin_sec, 3) if conflict else None
            ),
            "predecessor_id": conflict.leading_id if conflict else None,
        }

    def _metrics(
        self, flights: list[dict[str, Any]], t: float
    ) -> dict[str, float | int]:
        counts = {status.value: 0 for status in FlightStatus}
        for flight in flights:
            counts[flight["status"]] += 1

        landed = [flight for flight in flights if flight["status"] == FlightStatus.LANDED.value]
        avg_delay = fmean(flight["delay"] for flight in landed) if landed else 0.0
        total_fuel = sum(flight["fuel_proxy_kg"] for flight in landed)
        throughput = (
            len(landed) / (t / 3600.0) if t > 60.0 else 0.0
        )

        return {
            "total_flights": len(flights),
            "landed": len(landed),
            "final": counts[FlightStatus.FINAL.value],
            "holding": counts[FlightStatus.HOLDING.value],
            "en_route": counts[FlightStatus.EN_ROUTE.value],
            "scheduled": counts[FlightStatus.SCHEDULED.value],
            "avg_delay_sec": round(float(avg_delay), 3),
            "total_fuel_proxy_kg": round(float(total_fuel), 3),
            "throughput_per_hour": round(float(throughput), 3),
            "conflict_risk_pairs": int(self.result.metrics["conflict_risk_pairs"]),
            "separation_violations": int(self.result.metrics["separation_violations"]),
        }

    def _runway_snapshot(self, t: float) -> dict[str, Any]:
        current = None
        next_landing = None
        for aircraft in self.aircraft:
            actual = self._actual_time(aircraft)
            if 0.0 <= t - actual < self.config.runway_occupancy_sec:
                current = aircraft
            if actual > t:
                next_landing = aircraft
                break

        return {
            "id": self.runway,
            "status": "occupied" if current else "free",
            "current_flight": current.callsign if current else None,
            "next_flight": next_landing.callsign if next_landing else None,
            "occupancy_sec": self.config.runway_occupancy_sec,
        }

    def _alerts(
        self,
        metrics: dict[str, float | int],
        runway: dict[str, Any],
        t: float,
    ) -> list[dict[str, str]]:
        alerts: list[dict[str, str]] = []
        if metrics["separation_violations"] > 0:
            alerts.append(
                {
                    "severity": "critical",
                    "title": "Separation violation",
                    "message": f"{metrics['separation_violations']} actual separation violation(s) detected.",
                }
            )
        if metrics["conflict_risk_pairs"] > 0:
            alerts.append(
                {
                    "severity": "warning",
                    "title": "Schedule conflict risk",
                    "message": f"{metrics['conflict_risk_pairs']} consecutive pair(s) required separation intervention.",
                }
            )
        if metrics["holding"] >= 20:
            alerts.append(
                {
                    "severity": "warning",
                    "title": "Holding queue building",
                    "message": f"{metrics['holding']} aircraft are currently holding.",
                }
            )
        if metrics["avg_delay_sec"] >= 600:
            alerts.append(
                {
                    "severity": "warning",
                    "title": "High average delay",
                    "message": f"Average delay is {metrics['avg_delay_sec'] / 60:.1f} minutes for landed aircraft.",
                }
            )
        if runway["status"] == "occupied":
            alerts.append(
                {
                    "severity": "info",
                    "title": "Runway occupied",
                    "message": f"Runway {runway['id']} is occupied by {runway['current_flight']}.",
                }
            )
        if t >= self.end_time:
            alerts.append(
                {
                    "severity": "info",
                    "title": "Scenario complete",
                    "message": "All scheduled arrivals have landed.",
                }
            )
        return alerts[:6]

    def snapshot(self) -> dict[str, Any]:
        """Return the complete dashboard state as JSON-serializable data."""
        t = self.sim_time
        flights = [self._flight_snapshot(aircraft, t) for aircraft in self.aircraft]
        metrics = self._metrics(flights, t)
        runway = self._runway_snapshot(t)
        duration = max(1.0, self.end_time - self.start_time)

        return {
            "airport": {
                "icao": self.config.icao,
                "iata": self.config.iata,
                "name": self.config.name,
                "city": self.config.city,
                "country": self.config.country,
                "runway": self.runway,
                "map": self.map_data or None,
            },
            "scenario": {
                "strategy": self.strategy,
                "flights": self.flights,
                "seed": self.seed,
                "rate": self.rate,
                "speed": self.speed,
                "paused": self.paused,
                "start_time": self.start_time,
                "end_time": self.end_time,
                "duration": duration,
                "progress": max(0.0, min(1.0, (t - self.start_time) / duration)),
            },
            "sim_time": round(t, 3),
            "sim_time_text": format_time(t),
            "speed": self.speed,
            "paused": self.paused,
            "final_approach": {
                "faf_distance_nm": self.config.faf_distance_nm,
                "approach_speed_kts": self.config.final_approach_speed_kts,
                "speed_nm_per_sec": self.config.approach_speed_nm_per_sec,
                "angle_deg": self.config.approach_angle_deg,
                "duration_sec": self.final_approach_duration,
                "holding_lead_sec": HOLDING_LEAD_SEC,
                "en_route_lead_sec": EN_ROUTE_LEAD_SEC,
            },
            "metrics": metrics,
            "flights": flights,
            "runway": runway,
            "alerts": self._alerts(metrics, runway, t),
        }
