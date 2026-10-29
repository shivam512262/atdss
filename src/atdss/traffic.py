"""Synthetic arrival traffic generation."""

from __future__ import annotations

import random

from .config import AirportConfig, WakeCategory
from .models import Aircraft

_ORIGINS = (
    "DEL",
    "BOM",
    "BLR",
    "MAA",
    "HYD",
    "CCU",
    "AMD",
    "GOI",
    "TRV",
    "IXE",
    "PNQ",
    "JAI",
    "LKO",
    "IXC",
    "AGX",
    "IXM",
)
_AIRLINE_PREFIXES = ("6E", "AI", "IX", "QP", "SG", "9I")


def generate_traffic(
    config: AirportConfig,
    count: int,
    seed: int = 42,
    arrival_rate_per_hour: float | None = None,
    use_peak: bool = False,
    horizon_sec: float | None = None,
) -> list[Aircraft]:
    """Generate ``count`` arrivals and assign scheduled arrival times.

    Two modes are supported:

    * **Poisson mode** (default): exponential inter-arrival times at the
      configured or supplied rate. This is used for single runs and for a
      realistic queue build-up.
    * **Fixed-horizon mode** (``horizon_sec`` supplied): exactly ``count``
      arrivals are spread over a fixed operating window. This is used by the
      load-scaling experiment so that 100, 250, and 500 arrivals represent
      increasing demand within the same window rather than longer runs.

    The fixed-horizon mode ignores the time-of-day peak multiplier.
    """
    if count < 1:
        raise ValueError("count must be at least 1")

    rng = random.Random(seed)

    if horizon_sec is not None:
        if use_peak:
            raise ValueError(
                "use_peak is only supported in Poisson mode, not fixed-horizon mode"
            )
        if horizon_sec <= 0:
            raise ValueError("horizon_sec must be positive")
        scheduled_times = sorted(
            rng.uniform(0.0, float(horizon_sec)) for _ in range(count)
        )
    else:
        base_rate = (
            float(arrival_rate_per_hour)
            if arrival_rate_per_hour is not None
            else config.arrival_rate_per_hour
        )
        if base_rate <= 0:
            raise ValueError("arrival_rate_per_hour must be positive")

        scheduled_times = []
        current_time_sec = 0.0
        for _ in range(count):
            if use_peak:
                hour = (current_time_sec / 3600.0) % 24.0
                in_peak = config.peak_start_hour <= hour < config.peak_end_hour
                rate = base_rate * (config.peak_multiplier if in_peak else 1.0)
            else:
                rate = base_rate
            current_time_sec += rng.expovariate(rate / 3600.0)
            scheduled_times.append(current_time_sec)

    wake_categories = list(config.fleet_mix.keys())
    weights = [config.fleet_mix[wake] for wake in wake_categories]
    pools: dict[WakeCategory, list[str]] = {
        wake: [
            icao_type
            for icao_type, info in config.aircraft_types.items()
            if info.wake == wake
        ]
        for wake in wake_categories
    }

    runway = config.arrival_runway
    aircraft: list[Aircraft] = []
    for index, scheduled_time in enumerate(scheduled_times):
        wake = rng.choices(wake_categories, weights=weights, k=1)[0]
        pool = pools.get(wake) or [config.default_aircraft.icao_type]
        icao_type = rng.choice(pool)
        info = config.aircraft_info(icao_type)
        flight_number = (
            f"{_AIRLINE_PREFIXES[index % len(_AIRLINE_PREFIXES)]}{1000 + index}"
        )
        origin = _ORIGINS[index % len(_ORIGINS)]

        aircraft.append(
            Aircraft(
                id=f"AC{index:04d}",
                icao_type=info.icao_type,
                wake=info.wake,
                scheduled_arrival_sec=scheduled_time,
                callsign=flight_number,
                flight_number=flight_number,
                origin=origin,
                runway=runway,
            )
        )

    return aircraft
