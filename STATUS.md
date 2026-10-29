# AT-DSS Status: Simulation Milestone

**Date:** 2026-10-29  
**Scope:** Approximately 30% of the planned AT-DSS project, focused on the
simulation, baseline analysis, and live synthetic dashboard subsystem.
**Not included:** GA optimizer, XAI/SHAP, OpenAP/XGBoost fuel modeling, real
ADS-B/OpenSky ingestion, disruption scenarios, multi-airport operations, and
gate/taxi optimization.

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
- Live synthetic dashboard: FastAPI/WebSocket streaming, final-approach radar,
  holding stack, sortable flight board, runway timeline, alerts, flight detail
  drawer, pause/resume, speed control, reset, and scenario regeneration.
- Automated tests.

## Evidence

Run from `S:\Code\BE project\atdss-code`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Current result: **25 passed**.

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

Launch the live synthetic dashboard:

```powershell
.\.venv\Scripts\python.exe -m atdss.dashboard --flights 100 --seed 42 --rate 30 --speed 60 --open
```

The dashboard runs at <http://127.0.0.1:8000> and streams live state over a
WebSocket. It is a synthetic simulator view; no ADS-B/OpenSky feed is used.

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
2. Run the tests and show `25 passed`.
3. Run one FCFS case and one priority case; point out the sequence table.
4. Launch the live dashboard and show the clock advancing, final-approach
   aircraft, holding stack, flight board, runway timeline, alerts, and the
   click-through detail drawer. Demonstrate pause/resume, speed, reset, and
   scenario regeneration.
5. Generate and open the standalone HTML visual simulation; show aircraft
   moving along final approach, the holding queue, and live counters.
6. Run the 100/250/500 experiment and show the CSV and plots.
7. Explain the safety check: separation violations are zero because the
   scheduler enforces the wake matrix.
8. Explain the conflict-risk metric: it measures how often the original
   schedule was already below the required separation and therefore needed
   intervention.
9. State clearly that the fuel number is a holding-fuel proxy, not OpenAP or
   XGBoost output.
10. State that the optimizer, XAI, and real ADS-B ingestion are the next
    milestones.

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
| Live FastAPI/WebSocket dashboard | Complete (synthetic) |
| REST controls and scenario regeneration | Complete |
| Tests | 25 passing |
| GA optimizer | Not started |
| XAI/SHAP | Not started |
| OpenAP/XGBoost fuel | Not started |
| Real ADS-B/OpenSky feed | Not started |

The 30% estimate refers to the project's implementation scope, not to a formal
audit. The original simulation-only target was 15-20%; the added baselines,
conflict analysis, replication experiment, plots, live dashboard, tests, and
documentation support the higher estimate.

## Next milestone

1. Add a GA sequence optimizer that consumes the existing arbitrary-sequence
   API.
2. Compare GA against FCFS and priority on the same seeds.
3. Add an XAI summary for sequence changes.
4. Add OpenAP-based fuel estimation.
5. Optionally add a real ADS-B/OpenSky data-source adapter behind the existing
   live dashboard state layer.
