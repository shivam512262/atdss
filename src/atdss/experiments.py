"""Experiment runner for baseline sequencing strategies."""

from __future__ import annotations

import copy
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd

from .config import AirportConfig
from .conflict import analyze_sequence
from .metrics import compute_metrics
from .models import Aircraft, SimulationResult, Strategy
from .plots import plot_metric
from .sequencing import apply_sequence, sequence_for
from .simulation import run_sequence_simulation
from .traffic import generate_traffic


def _normalise_strategy(strategy: Strategy | str) -> str:
    value = strategy.value if isinstance(strategy, Strategy) else str(strategy).lower()
    if value not in {item.value for item in Strategy}:
        raise ValueError(f"Unknown sequencing strategy: {strategy!r}")
    return value


def run_strategy_on_traffic(
    aircraft: list[Aircraft],
    config: AirportConfig,
    strategy: Strategy | str,
) -> SimulationResult:
    """Copy traffic, build a sequence, enforce separation, simulate, and score."""
    strategy_name = _normalise_strategy(strategy)
    working = copy.deepcopy(aircraft)
    for item in working:
        item.reset_schedule()

    sequence = sequence_for(strategy_name, working)
    apply_sequence(sequence, config)
    conflicts = analyze_sequence(sequence, config)

    started = time.perf_counter()
    result = run_sequence_simulation(sequence, config, strategy_name)
    runtime_sec = time.perf_counter() - started

    result.conflicts = conflicts
    result.metrics = compute_metrics(
        sequence=sequence,
        conflicts=conflicts,
        strategy=strategy_name,
        start_time_sec=result.start_time_sec,
        end_time_sec=result.end_time_sec,
        runtime_sec=runtime_sec,
    )
    return result


def run_single(
    config: AirportConfig,
    strategy: Strategy | str,
    flights: int,
    seed: int = 42,
    use_peak: bool = False,
    arrival_rate_per_hour: float | None = None,
) -> SimulationResult:
    """Run one strategy on one generated traffic sample."""
    traffic = generate_traffic(
        config,
        count=flights,
        seed=seed,
        use_peak=use_peak,
        arrival_rate_per_hour=arrival_rate_per_hour,
    )
    return run_strategy_on_traffic(traffic, config, strategy)


def _sequence_rows(result: SimulationResult) -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    for aircraft in result.sequence:
        rows.append(
            {
                "strategy": result.strategy,
                "position": aircraft.sequence_position,
                "aircraft_id": aircraft.id,
                "callsign": aircraft.callsign,
                "icao_type": aircraft.icao_type,
                "wake": aircraft.wake.value,
                "scheduled_arrival_sec": round(aircraft.scheduled_arrival_sec, 3),
                "assigned_landing_sec": round(
                    aircraft.assigned_or_scheduled_sec, 3
                ),
                "actual_landing_sec": round(
                    aircraft.actual_landing_sec
                    if aircraft.actual_landing_sec is not None
                    else -1.0,
                    3,
                ),
                "delay_sec": round(aircraft.delay_sec, 3),
                "fuel_proxy_kg": round(aircraft.fuel_proxy_kg, 3),
            }
        )
    return rows


def _write_summary(
    dataframe: pd.DataFrame,
    output_path: Path,
    config: AirportConfig,
    horizon_hours: float,
) -> Path:
    grouped = dataframe.groupby(["strategy", "flights"]).agg(
        avg_delay_sec_mean=("avg_delay_sec", "mean"),
        avg_delay_sec_std=("avg_delay_sec", "std"),
        max_delay_sec_mean=("max_delay_sec", "mean"),
        throughput_per_hour_mean=("throughput_per_hour", "mean"),
        conflict_risk_pairs_mean=("conflict_risk_pairs", "mean"),
        separation_violations_mean=("separation_violations", "mean"),
        min_margin_sec_mean=("min_margin_sec", "mean"),
        total_fuel_proxy_kg_mean=("total_fuel_proxy_kg", "mean"),
        runtime_sec_mean=("runtime_sec", "mean"),
    ).reset_index()

    lines = [
        "# AT-DSS simulation experiment summary",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        f"Airport: {config.icao} ({config.name})",
        f"Final-approach speed: {config.final_approach_speed_kts:.0f} kt",
        f"Demand window: {horizon_hours:.1f} h for every traffic volume",
        "",
        "## Aggregate results",
        "",
        "| Strategy | Flights | Avg delay (s) | Max delay (s) | Throughput/h | "
        "Conflict-risk pairs | Separation violations | Min margin (s) | "
        "Fuel proxy (kg) | Sim runtime (s) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for row in grouped.itertuples(index=False):
        lines.append(
            "| {strategy} | {flights} | {avg_delay:.1f} +/- {avg_std:.1f} | "
            "{max_delay:.1f} | {throughput:.1f} | {risk:.1f} | {violations:.1f} | "
            "{margin:.1f} | {fuel:.1f} | {runtime:.3f} |".format(
                strategy=str(row.strategy).upper(),
                flights=int(row.flights),
                avg_delay=row.avg_delay_sec_mean,
                avg_std=0.0 if pd.isna(row.avg_delay_sec_std) else row.avg_delay_sec_std,
                max_delay=row.max_delay_sec_mean,
                throughput=row.throughput_per_hour_mean,
                risk=row.conflict_risk_pairs_mean,
                violations=row.separation_violations_mean,
                margin=row.min_margin_sec_mean,
                fuel=row.total_fuel_proxy_kg_mean,
                runtime=row.runtime_sec_mean,
            )
        )

    lines.extend(
        [
            "",
            "## Metric definitions",
            "",
            "- **Avg delay**: mean difference between actual landing and scheduled arrival.",
            "- **Conflict-risk pairs**: consecutive pairs whose pre-sequencing scheduled "
            "gap was below the required wake-separation gap.",
            "- **Separation violations**: consecutive pairs whose actual landing gap is "
            "below required separation. This should be zero because the scheduler "
            "enforces separation; a nonzero value indicates a bug.",
            "- **Min margin**: smallest actual-gap minus required-gap across pairs.",
            "- **Fuel proxy**: delay seconds multiplied by a wake-category fuel-flow proxy. "
            "This is not an OpenAP/XGBoost fuel model.",
            "",
            "## Interpretation",
            "",
            "These are baseline results, not optimizer results. FCFS preserves scheduled "
            "order; wake priority moves Heavy aircraft earlier and can trade delay between "
            "traffic classes. The GA optimizer, XAI layer, and OpenAP-based fuel model are "
            "outside this milestone.",
            "",
        ]
    )

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def run_traffic_scaling(
    config: AirportConfig,
    counts: Iterable[int] = (100, 250, 500),
    reps: int = 5,
    strategies: Iterable[Strategy | str] = (Strategy.FCFS, Strategy.PRIORITY),
    seed_base: int = 42,
    output_dir: str | Path = "results",
    use_peak: bool = False,
    arrival_rate_per_hour: float | None = None,
    horizon_hours: float = 12.0,
) -> tuple[pd.DataFrame, Path]:
    """Run the 100/250/500 traffic-scaling experiment and write artifacts."""
    counts = [int(value) for value in counts]
    strategy_names = [_normalise_strategy(value) for value in strategies]
    if not counts:
        raise ValueError("At least one flight count is required")
    if reps < 1:
        raise ValueError("reps must be at least 1")
    if horizon_hours <= 0:
        raise ValueError("horizon_hours must be positive")

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, float | str]] = []
    sample_rows: list[dict[str, float | str]] = []

    for flights in counts:
        for rep in range(reps):
            seed = seed_base + rep
            traffic = generate_traffic(
                config,
                count=flights,
                seed=seed,
                use_peak=use_peak,
                arrival_rate_per_hour=arrival_rate_per_hour,
                horizon_sec=horizon_hours * 3600.0,
            )

            for strategy in strategy_names:
                result = run_strategy_on_traffic(traffic, config, strategy)
                row: dict[str, float | str] = dict(result.metrics)
                row["rep"] = rep
                row["seed"] = seed
                rows.append(row)

                if flights == counts[0] and rep == 0:
                    sample_rows.extend(_sequence_rows(result))

    dataframe = pd.DataFrame(rows)
    comparison_path = output / "baseline_comparison.csv"
    dataframe.to_csv(comparison_path, index=False)

    if sample_rows:
        pd.DataFrame(sample_rows).to_csv(
            output / "sample_sequence.csv", index=False
        )

    summary_path = _write_summary(
        dataframe, output / "summary.md", config, horizon_hours
    )

    plot_metric(
        dataframe,
        metric="avg_delay_sec",
        ylabel="Average delay (s)",
        output_path=output / "fig_delay_vs_traffic.png",
        title="Average arrival delay by traffic volume",
    )
    plot_metric(
        dataframe,
        metric="conflict_risk_pairs",
        ylabel="Conflict-risk pairs",
        output_path=output / "fig_conflict_risk_vs_traffic.png",
        title="Separation conflict risk by traffic volume",
    )
    plot_metric(
        dataframe,
        metric="total_fuel_proxy_kg",
        ylabel="Holding fuel proxy (kg)",
        output_path=output / "fig_fuel_proxy_vs_traffic.png",
        title="Holding-fuel proxy by traffic volume",
    )

    summary = pd.read_csv(summary_path, sep="|", skiprows=8) if False else None
    return dataframe, summary_path  # type: ignore[return-value]
