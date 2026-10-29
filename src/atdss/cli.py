"""Command-line interface for the AT-DSS simulation milestone."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .config import load_config
from .experiments import run_single, run_traffic_scaling
from .models import SimulationResult


def _print_single(result: SimulationResult, airport: str) -> None:
    metrics = result.metrics
    print(f"\nAT-DSS baseline run - {airport}")
    print("=" * 64)
    print(f"Strategy:                 {str(metrics['strategy']).upper()}")
    print(f"Flights:                  {int(metrics['flights'])}")
    print(f"Landed:                   {int(metrics['landed'])}")
    print(f"Average delay:            {float(metrics['avg_delay_sec']):.1f} s")
    print(f"Maximum delay:            {float(metrics['max_delay_sec']):.1f} s")
    print(f"Throughput:               {float(metrics['throughput_per_hour']):.1f} arrivals/h")
    print(f"Conflict-risk pairs:      {int(metrics['conflict_risk_pairs'])}")
    print(f"Tight pairs:              {int(metrics['tight_pairs'])}")
    print(f"Separation violations:    {int(metrics['separation_violations'])}")
    print(f"Minimum separation margin:{float(metrics['min_margin_sec']):.1f} s")
    print(f"Holding fuel proxy:       {float(metrics['total_fuel_proxy_kg']):.1f} kg")
    print(f"Simulation runtime:       {float(metrics['runtime_sec']):.3f} s")

    print("\nFirst 12 sequenced arrivals:")
    print(
        f"{'pos':>3} {'aircraft':>10} {'type':>6} {'wake':>4} "
        f"{'sched(s)':>9} {'assigned(s)':>11} {'actual(s)':>10} "
        f"{'delay(s)':>8} {'fuel(kg)':>9}"
    )
    for aircraft in result.sequence[:12]:
        actual = (
            aircraft.actual_landing_sec
            if aircraft.actual_landing_sec is not None
            else -1.0
        )
        print(
            f"{aircraft.sequence_position:>3} {aircraft.callsign:>10} "
            f"{aircraft.icao_type:>6} {aircraft.wake.value:>4} "
            f"{aircraft.scheduled_arrival_sec:>9.1f} "
            f"{aircraft.assigned_or_scheduled_sec:>11.1f} "
            f"{actual:>10.1f} {aircraft.delay_sec:>8.1f} "
            f"{aircraft.fuel_proxy_kg:>9.1f}"
        )
    print()


def _print_experiment(dataframe: pd.DataFrame) -> None:
    print("\nAT-DSS traffic-scaling experiment")
    print("=" * 78)
    grouped = dataframe.groupby(["strategy", "flights"]).agg(
        avg_delay=("avg_delay_sec", "mean"),
        conflict_risk=("conflict_risk_pairs", "mean"),
        violations=("separation_violations", "mean"),
        fuel=("total_fuel_proxy_kg", "mean"),
        runtime=("runtime_sec", "mean"),
    ).reset_index()
    print(
        f"{'strategy':>10} {'flights':>8} {'avg delay(s)':>13} "
        f"{'risk pairs':>11} {'violations':>11} {'fuel proxy(kg)':>15} "
        f"{'runtime(s)':>11}"
    )
    for row in grouped.itertuples(index=False):
        print(
            f"{str(row.strategy).upper():>10} {int(row.flights):>8} "
            f"{row.avg_delay:>13.1f} {row.conflict_risk:>11.1f} "
            f"{row.violations:>11.1f} {row.fuel:>15.1f} "
            f"{row.runtime:>11.3f}"
        )
    print()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="AT-DSS arrival-sequencing simulation milestone"
    )
    parser.add_argument("--config", type=Path, default=None, help="Airport YAML path")
    parser.add_argument(
        "--strategy",
        choices=["fcfs", "priority"],
        default="fcfs",
        help="Baseline strategy for a single run",
    )
    parser.add_argument("--flights", type=int, default=100, help="Arrivals in a single run")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for a single run")
    parser.add_argument(
        "--rate",
        type=float,
        default=None,
        help="Arrival rate in aircraft/hour (default: config value)",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Run the multi-volume experiment with plots and CSV output",
    )
    parser.add_argument(
        "--counts",
        nargs="+",
        type=int,
        default=[100, 250, 500],
        help="Traffic volumes for --compare",
    )
    parser.add_argument(
        "--strategies",
        nargs="+",
        choices=["fcfs", "priority"],
        default=["fcfs", "priority"],
        help="Strategies for --compare",
    )
    parser.add_argument("--reps", type=int, default=5, help="Replications per volume")
    parser.add_argument(
        "--horizon-hours",
        type=float,
        default=12.0,
        help="Fixed demand window for --compare (default: 12 h)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results"),
        help="Directory for CSV, markdown, and plots",
    )
    parser.add_argument(
        "--peak",
        action="store_true",
        help="Enable the time-of-day peak multiplier for a single Poisson run",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config(args.config)

    if args.compare:
        dataframe, summary_path = run_traffic_scaling(
            config=config,
            counts=args.counts,
            reps=args.reps,
            strategies=args.strategies,
            seed_base=args.seed,
            output_dir=args.output_dir,
            use_peak=args.peak,
            arrival_rate_per_hour=args.rate,
            horizon_hours=args.horizon_hours,
        )
        _print_experiment(dataframe)
        print(f"Artifacts written to: {args.output_dir.resolve()}")
        print(f"Summary: {summary_path.resolve()}")
        return 0

    result = run_single(
        config=config,
        strategy=args.strategy,
        flights=args.flights,
        seed=args.seed,
        use_peak=args.peak,
        arrival_rate_per_hour=args.rate,
    )
    _print_single(result, f"{config.icao} ({config.name})")
    return 0
