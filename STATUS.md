# AT-DSS Status: Simulation Milestone

**Date:** 2026-10-29  
**Scope:** Approximately 30% of the planned AT-DSS project, focused on the
simulation and baseline-analysis subsystem.  
**Not included:** GA optimizer, XAI/SHAP, OpenAP/XGBoost fuel modeling,
dashboard, disruption scenarios, multi-airport operations, and gate/taxi
optimization.

## What can be demonstrated

- Synthetic arrival traffic for EHAM/Schiphol with a configurable fleet mix.
- FCFS baseline.
- Bounded wake-priority baseline.
- ICAO-style wake-separation enforcement.
- Arbitrary-sequence API for a future optimizer.
- SimPy single-runway execution.
- Consecutive-pair conflict-risk analysis.
- Delay, throughput, separation, and holding-fuel-proxy metrics.
- 100/250/500-arrival experiment with five replications.
- CSV, Markdown, and PNG outputs.
- Standalone HTML real-time animation with final-approach movement, runway
  occupancy, holding queue, and live counters.
- Automated tests.

## Evidence

Run from `S:\Code\BE project\atdss-code`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Current result: **13 passed**.

```powershell
.\.venv\Scripts\python.exe -m atdss --strategy fcfs --flights 100 --seed 42 --rate 30
.\.venv\Scripts\python.exe -m atdss --strategy priority --flights 100 --seed 42 --rate 30
```

```powershell
.\.venv\Scripts\python.exe -m atdss --compare --counts 100 250 500 --reps 5 --seed 42
```

Generate the visual simulation:

```powershell
.\.venv\Scripts\python.exe -m atdss --strategy fcfs --flights 100 --seed 42 --rate 30 --visual --open
```

The generated `results/simulation_fcfs_100.html` plays the arrival sequence in
a browser. It shows the 10 NM final approach, wake-separation gaps, runway
occupancy, holding queue, and live counters.

## Results snapshot

Seed 42, five replications, fixed 12-hour demand window:

| Strategy | Flights | Avg delay (s) | Conflict-risk pairs | Separation violations | Fuel proxy (kg) |
|---|---:|---:|---:|---:|---:|
| FCFS | 100 | 9.7 | 17.0 | 0 | 625 |
| FCFS | 250 | 65.6 | 106.8 | 0 | 10,902 |
| FCFS | 500 | 2,253.5 | 327.0 | 0 | 758,653 |
| Priority | 100 | 24.1 | 17.2 | 0 | 1,215 |
| Priority | 250 | 92.3 | 98.0 | 0 | 12,725 |
| Priority | 500 | 2,302.0 | 274.0 | 0 | 762,648 |

Files are in `results/`:

- `baseline_comparison.csv`
- `sample_sequence.csv`
- `summary.md`
- `fig_delay_vs_traffic.png`
- `fig_conflict_risk_vs_traffic.png`
- `fig_fuel_proxy_vs_traffic.png`

## How to present it

1. Show the repository layout and state that this is a separate, git-ready
   implementation.
2. Run the tests and show `13 passed`.
3. Run one FCFS case and one priority case; point out the sequence table.
4. Generate and open the HTML visual simulation; show aircraft moving along
   final approach, the holding queue, and live counters.
5. Run the 100/250/500 experiment and show the CSV and plots.
6. Explain the safety check: separation violations are zero because the
   scheduler enforces the wake matrix.
7. Explain the conflict-risk metric: it measures how often the original
   schedule was already below the required separation and therefore needed
   intervention.
8. State clearly that the fuel number is a holding-fuel proxy, not OpenAP or
   XGBoost output.
9. State that the optimizer, XAI, and dashboard are the next milestones.

## Why this is roughly 30%

| Component | Status |
|---|---|
| Configuration and airport data | Complete for EHAM |
| Traffic generation | Complete |
| FCFS baseline | Complete |
| Priority baseline | Complete |
| Wake separation | Complete |
| Arbitrary sequence input | Complete |
| SimPy runway execution | Complete |
| Conflict-risk analysis | Complete |
| Metrics | Complete |
| 100/250/500 experiment | Complete |
| Plots and CSV outputs | Complete |
| Real-time HTML visual simulation | Complete |
| Tests | 13 passing |
| GA optimizer | Not started |
| XAI/SHAP | Not started |
| OpenAP/XGBoost fuel | Not started |
| Interactive dashboard | Not started |

The 30% estimate refers to the project's implementation scope, not to a formal
audit. The original simulation-only target was 15-20%; the added baselines,
conflict analysis, replication experiment, plots, tests, and documentation
support the higher estimate.

## Next milestone

1. Add a GA sequence optimizer that consumes the existing arbitrary-sequence
   API.
2. Compare GA against FCFS and priority on the same seeds.
3. Add an XAI summary for sequence changes.
4. Add OpenAP-based fuel estimation.
5. Build a small Streamlit dashboard for a live demo.
