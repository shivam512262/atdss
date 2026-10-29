"""Plot generation for the traffic-scaling experiment."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd


def plot_metric(
    dataframe: pd.DataFrame,
    metric: str,
    ylabel: str,
    output_path: str | Path,
    title: str,
) -> Path:
    """Plot mean and standard deviation of a metric by strategy and volume."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    grouped = (
        dataframe.groupby(["strategy", "flights"])[metric]
        .agg(["mean", "std"])
        .reset_index()
    )

    figure, axis = plt.subplots(figsize=(7.2, 4.2))
    for strategy, group in grouped.groupby("strategy"):
        group = group.sort_values("flights")
        axis.errorbar(
            group["flights"],
            group["mean"],
            yerr=group["std"].fillna(0.0),
            marker="o",
            capsize=4,
            linewidth=2,
            label=strategy.upper(),
        )

    axis.set_title(title)
    axis.set_xlabel("Arrivals in run")
    axis.set_ylabel(ylabel)
    axis.grid(True, alpha=0.3)
    axis.legend()
    figure.tight_layout()
    figure.savefig(output, dpi=160)
    plt.close(figure)
    return output
