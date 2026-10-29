"""Metric computation for a simulated arrival sequence."""

from __future__ import annotations

from statistics import fmean

from .conflict import summarize_conflicts
from .models import Aircraft, ConflictRisk


def compute_metrics(
    sequence: list[Aircraft],
    conflicts: list[ConflictRisk],
    strategy: str,
    start_time_sec: float,
    end_time_sec: float,
    runtime_sec: float = 0.0,
) -> dict[str, float | str]:
    """Compute operational, safety, and fuel-proxy metrics."""
    if not sequence:
        raise ValueError("Cannot compute metrics for an empty sequence")

    delays = [aircraft.delay_sec for aircraft in sequence]
    fuels = [aircraft.fuel_proxy_kg for aircraft in sequence]
    landed = sum(aircraft.actual_landing_sec is not None for aircraft in sequence)
    horizon_sec = max(end_time_sec - start_time_sec, 1.0)
    conflict_metrics = summarize_conflicts(conflicts)

    return {
        "strategy": strategy,
        "flights": len(sequence),
        "landed": landed,
        "completion_rate": landed / len(sequence),
        "avg_delay_sec": float(fmean(delays)),
        "total_delay_sec": float(sum(delays)),
        "max_delay_sec": float(max(delays)),
        "throughput_per_hour": float(landed / (horizon_sec / 3600.0)),
        "total_fuel_proxy_kg": float(sum(fuels)),
        "avg_fuel_proxy_kg": float(fmean(fuels)),
        **conflict_metrics,
        "horizon_sec": float(horizon_sec),
        "start_time_sec": float(start_time_sec),
        "end_time_sec": float(end_time_sec),
        "runtime_sec": float(runtime_sec),
    }
