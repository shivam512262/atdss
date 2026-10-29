"""Consecutive-pair separation and conflict-risk analysis.

The scheduler enforces hard separation, so a correct run has zero landing-gap
violations. The useful safety signal in this milestone is therefore:

* ``conflict_risk``: the original schedule gap was below the required gap, so
  the pair required controller or optimizer intervention.
* ``tight``: the post-sequencing gap is below ``conflict_margin_ratio`` times
  the required gap.
* ``separation_pressure_sec``: how much delay the pair's separation requirement
  forced relative to the original schedule.
"""

from __future__ import annotations

from statistics import fmean

from .config import AirportConfig
from .models import Aircraft, ConflictRisk


def analyze_sequence(
    sequence: list[Aircraft], config: AirportConfig
) -> list[ConflictRisk]:
    """Analyze consecutive pairs in an assigned landing sequence."""
    results: list[ConflictRisk] = []

    for leading, following in zip(sequence, sequence[1:]):
        required_sec = config.separation_sec_between(leading.wake, following.wake)
        scheduled_gap = following.scheduled_arrival_sec - leading.scheduled_arrival_sec
        actual_gap = (
            following.assigned_or_scheduled_sec - leading.assigned_or_scheduled_sec
        )
        margin = actual_gap - required_sec

        results.append(
            ConflictRisk(
                leading_id=leading.id,
                following_id=following.id,
                leading_wake=leading.wake,
                following_wake=following.wake,
                required_sep_sec=required_sec,
                scheduled_gap_sec=scheduled_gap,
                actual_gap_sec=actual_gap,
                margin_sec=margin,
                conflict_risk=scheduled_gap < required_sec - 1e-9,
                tight=actual_gap < required_sec * config.conflict_margin_ratio - 1e-9,
                violation=actual_gap < required_sec - 1e-6,
            )
        )

    return results


def summarize_conflicts(conflicts: list[ConflictRisk]) -> dict[str, float]:
    """Aggregate pair-level conflict results into metrics."""
    if not conflicts:
        return {
            "conflict_risk_pairs": 0.0,
            "tight_pairs": 0.0,
            "separation_violations": 0.0,
            "min_margin_sec": 0.0,
            "avg_margin_sec": 0.0,
            "separation_pressure_sec": 0.0,
        }

    margins = [item.margin_sec for item in conflicts]
    min_margin = min(margins)
    if -1e-6 < min_margin < 0.0:
        # Floating-point round-off at an exactly minimum-separation gap.
        min_margin = 0.0
    pressure = [
        max(0.0, item.required_sep_sec - item.scheduled_gap_sec)
        for item in conflicts
    ]

    return {
        "conflict_risk_pairs": float(sum(item.conflict_risk for item in conflicts)),
        "tight_pairs": float(sum(item.tight for item in conflicts)),
        "separation_violations": float(sum(item.violation for item in conflicts)),
        "min_margin_sec": float(min_margin),
        "avg_margin_sec": float(fmean(margins)),
        "separation_pressure_sec": float(sum(pressure)),
    }
