"""Tests for the simulation milestone."""

from __future__ import annotations

import pytest

from atdss.config import WakeCategory, load_config
from atdss.conflict import analyze_sequence, summarize_conflicts
from atdss.experiments import run_single
from atdss.models import Aircraft
from atdss.sequencing import apply_sequence, fcfs_sequence, priority_sequence
from atdss.traffic import generate_traffic


@pytest.fixture(scope="module")
def config():
    return load_config()


def test_config_loads(config):
    assert config.icao == "EHAM"
    assert config.separation_nm_between(
        WakeCategory.HEAVY, WakeCategory.MEDIUM
    ) == pytest.approx(5.0)
    assert config.fuel_flow_kg_s[WakeCategory.HEAVY] == pytest.approx(1.2)
    assert config.runway_occupancy_sec > 0


def test_traffic_is_reproducible(config):
    first = generate_traffic(config, count=50, seed=7)
    second = generate_traffic(config, count=50, seed=7)
    assert [item.scheduled_arrival_sec for item in first] == [
        item.scheduled_arrival_sec for item in second
    ]
    assert all(item.scheduled_arrival_sec > 0 for item in first)


def test_fcfs_preserves_scheduled_order(config):
    traffic = generate_traffic(config, count=60, seed=11)
    sequence = fcfs_sequence(traffic)
    times = [item.scheduled_arrival_sec for item in sequence]
    assert times == sorted(times)


def test_priority_orders_by_bounded_wake_bonus(config):
    traffic = generate_traffic(config, count=60, seed=12)
    sequence = priority_sequence(traffic)
    bonus = {"H": 180.0, "M": 60.0, "L": 0.0}
    keys = [
        (item.scheduled_arrival_sec - bonus[item.wake.value], item.scheduled_arrival_sec)
        for item in sequence
    ]
    assert keys == sorted(keys)


def test_apply_sequence_enforces_wake_separation(config):
    traffic = generate_traffic(config, count=100, seed=13)
    sequence = apply_sequence(fcfs_sequence(traffic), config)

    for leading, following in zip(sequence, sequence[1:]):
        required = config.separation_sec_between(leading.wake, following.wake)
        gap = following.assigned_or_scheduled_sec - leading.assigned_or_scheduled_sec
        assert gap >= required - 1e-6

    conflicts = analyze_sequence(sequence, config)
    assert summarize_conflicts(conflicts)["separation_violations"] == 0


def test_conflict_risk_identifies_forced_intervention(config):
    leading = Aircraft(
        id="H1",
        icao_type="B77W",
        wake=WakeCategory.HEAVY,
        scheduled_arrival_sec=0.0,
    )
    following = Aircraft(
        id="M1",
        icao_type="A320",
        wake=WakeCategory.MEDIUM,
        scheduled_arrival_sec=10.0,
    )
    sequence = apply_sequence([leading, following], config)
    conflicts = analyze_sequence(sequence, config)
    summary = summarize_conflicts(conflicts)

    assert len(conflicts) == 1
    assert conflicts[0].conflict_risk is True
    assert conflicts[0].violation is False
    assert conflicts[0].tight is True
    assert summary["separation_violations"] == 0
    assert summary["separation_pressure_sec"] > 0


def test_single_run_completes_and_scores(config):
    result = run_single(config, strategy="fcfs", flights=50, seed=99)
    metrics = result.metrics

    assert metrics["flights"] == 50
    assert metrics["landed"] == 50
    assert metrics["completion_rate"] == pytest.approx(1.0)
    assert metrics["separation_violations"] == 0
    assert metrics["avg_delay_sec"] >= 0
    assert metrics["total_fuel_proxy_kg"] >= 0
    assert metrics["throughput_per_hour"] > 0


def test_unknown_strategy_rejected(config):
    traffic = generate_traffic(config, count=5, seed=1)
    with pytest.raises(ValueError):
        from atdss.experiments import run_strategy_on_traffic

        run_strategy_on_traffic(traffic, config, "not-a-strategy")


def test_fixed_horizon_traffic_stays_in_window(config):
    horizon_sec = 4 * 3600.0
    traffic = generate_traffic(
        config, count=40, seed=5, horizon_sec=horizon_sec
    )
    times = [item.scheduled_arrival_sec for item in traffic]
    assert len(times) == 40
    assert min(times) >= 0.0
    assert max(times) <= horizon_sec
    with pytest.raises(ValueError):
        generate_traffic(
            config, count=40, seed=5, horizon_sec=horizon_sec, use_peak=True
        )


def test_compare_writes_artifacts(config, tmp_path):
    from atdss.experiments import run_traffic_scaling

    dataframe, summary_path = run_traffic_scaling(
        config=config,
        counts=[20, 40],
        reps=1,
        strategies=["fcfs", "priority"],
        seed_base=3,
        output_dir=tmp_path,
    )

    assert len(dataframe) == 4
    assert set(dataframe["strategy"]) == {"fcfs", "priority"}
    assert summary_path.exists()
    for name in (
        "baseline_comparison.csv",
        "sample_sequence.csv",
        "summary.md",
        "fig_delay_vs_traffic.png",
        "fig_conflict_risk_vs_traffic.png",
        "fig_fuel_proxy_vs_traffic.png",
    ):
        assert (tmp_path / name).exists()
