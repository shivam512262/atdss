"""Airport configuration loading for the AT-DSS simulation milestone."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import yaml


class WakeCategory(str, Enum):
    """ICAO wake-turbulence categories used by the separation matrix."""

    HEAVY = "H"
    MEDIUM = "M"
    LIGHT = "L"


@dataclass(frozen=True)
class AircraftTypeInfo:
    icao_type: str
    wake: WakeCategory
    openap_name: str
    mass_kg: float


@dataclass
class AirportConfig:
    """Parsed airport and simulation configuration."""

    icao: str
    name: str
    separation_nm: dict[WakeCategory, dict[WakeCategory, float]]
    faf_distance_nm: float
    final_approach_speed_kts: float
    approach_angle_deg: float
    threshold_crossing_height_ft: float
    fleet_mix: dict[WakeCategory, float]
    aircraft_types: dict[str, AircraftTypeInfo]
    default_aircraft: AircraftTypeInfo
    arrival_rate_per_hour: float
    peak_multiplier: float
    peak_start_hour: float
    peak_end_hour: float
    max_simulation_time_sec: float
    runway_occupancy_sec: float
    taxi_time_sec: float
    conflict_margin_ratio: float
    fuel_flow_kg_s: dict[WakeCategory, float]
    raw: dict[str, Any]

    @property
    def approach_speed_nm_per_sec(self) -> float:
        """Final approach speed converted from knots to NM/second."""
        return self.final_approach_speed_kts / 3600.0

    def separation_nm_between(
        self, leading: WakeCategory, following: WakeCategory
    ) -> float:
        """Required wake-turbulence separation in nautical miles."""
        return self.separation_nm.get(leading, {}).get(following, 3.0)

    def separation_sec_between(
        self, leading: WakeCategory, following: WakeCategory
    ) -> float:
        """Required separation expressed as time at final-approach speed."""
        return self.separation_nm_between(leading, following) / self.approach_speed_nm_per_sec

    def aircraft_info(self, icao_type: str) -> AircraftTypeInfo:
        """Look up aircraft metadata, falling back to the configured default."""
        return self.aircraft_types.get(icao_type, self.default_aircraft)


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "ehamp.yaml"


def load_config(path: str | Path | None = None) -> AirportConfig:
    """Load an airport YAML file into an :class:`AirportConfig`."""
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    if not config_path.exists():
        raise FileNotFoundError(
            f"Airport config not found: {config_path}. "
            "Run commands from the atdss-code project root or pass --config."
        )

    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)

    airport = raw["airport"]
    approach = raw["approach"]
    traffic = raw["traffic"]
    simulation = raw["simulation"]
    conflict = raw["conflict"]
    fuel_proxy = raw.get("fuel_proxy", {"H": 1.2, "M": 0.5, "L": 0.2})

    separation_nm: dict[WakeCategory, dict[WakeCategory, float]] = {}
    for leading, followers in raw["separation_nm"].items():
        lead_wake = WakeCategory(leading)
        separation_nm[lead_wake] = {
            WakeCategory(following): float(value)
            for following, value in followers.items()
        }

    fleet_mix = {
        WakeCategory(category): float(value)
        for category, value in raw["fleet_mix"].items()
    }

    aircraft_types: dict[str, AircraftTypeInfo] = {}
    for icao_type, info in raw["aircraft_types"].items():
        aircraft_types[icao_type] = AircraftTypeInfo(
            icao_type=icao_type,
            wake=WakeCategory(info["wake"]),
            openap_name=str(info["openap"]),
            mass_kg=float(info["mass_kg"]),
        )

    default_info = raw["default_aircraft"]
    default_aircraft = AircraftTypeInfo(
        icao_type="DEFAULT",
        wake=WakeCategory(default_info["wake"]),
        openap_name=str(default_info["openap"]),
        mass_kg=float(default_info["mass_kg"]),
    )

    return AirportConfig(
        icao=str(airport["icao"]),
        name=str(airport["name"]),
        separation_nm=separation_nm,
        faf_distance_nm=float(approach["final_approach_fix_distance_nm"]),
        final_approach_speed_kts=float(approach["final_approach_speed_kts"]),
        approach_angle_deg=float(approach["approach_angle_deg"]),
        threshold_crossing_height_ft=float(approach["threshold_crossing_height_ft"]),
        fleet_mix=fleet_mix,
        aircraft_types=aircraft_types,
        default_aircraft=default_aircraft,
        arrival_rate_per_hour=float(traffic["arrival_rate_per_hour"]),
        peak_multiplier=float(traffic["peak_multiplier"]),
        peak_start_hour=float(traffic["peak_start_hour"]),
        peak_end_hour=float(traffic["peak_end_hour"]),
        max_simulation_time_sec=float(simulation["max_simulation_time_sec"]),
        runway_occupancy_sec=float(simulation.get("runway_occupancy_sec", 40.0)),
        taxi_time_sec=float(simulation.get("taxi_time_sec", 300.0)),
        conflict_margin_ratio=float(conflict.get("conflict_margin_ratio", 1.2)),
        fuel_flow_kg_s={
            WakeCategory(category): float(value)
            for category, value in fuel_proxy.items()
        },
        raw=raw,
    )
