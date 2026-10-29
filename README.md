# AT-DSS Simulation Milestone

This repository contains the simulation-first slice of the AT-DSS (AI-assisted
airport arrival sequencing decision-support) project. It is a standalone,
runnable package that demonstrates the baseline arrival-sequencing pipeline and
a live synthetic operations dashboard. The GA optimizer and XAI layer remain
future work.

See `STATUS.md` for the milestone checklist, results snapshot, and a suggested
demo sequence.

## What is implemented

- Synthetic Poisson arrival traffic with a configurable fleet mix.
- EHAM/Schiphol single-runway configuration.
- FCFS (first-come, first-served) baseline.
- Wake-priority baseline (Heavy, then Medium, then Light).
- Wake-turbulence separation enforcement using the ICAO-style separation matrix.
- Arbitrary-sequence API, so a future GA can supply a landing order.
- SimPy discrete-event execution with a single runway and runway occupancy.
- Consecutive-pair separation analysis:
  - hard separation violations (must be zero);
  - conflict-risk pairs from the pre-sequencing schedule;
  - tight pairs based on a margin threshold;
  - minimum and average separation margin;
  - separation-pressure seconds.
- Metrics: delay, maximum delay, throughput, holding-fuel proxy, conflict risk,
  violations, and runtime.
- 100/250/500-arrival traffic-scaling experiment with 5 replications.
- CSV, Markdown summary, and PNG plots.
- Standalone HTML real-time animation of final approach, runway occupancy,
  holding queue, and live metrics.
- Live synthetic operations dashboard served by FastAPI and WebSocket:
  - final-approach radar with aircraft positions and holding stack;
  - sortable, searchable flight board with schedule, ETA, status, and delay;
  - runway timeline with scheduled, assigned, and actual landing markers;
  - live alerts for separation risk, queue build-up, and runway occupancy;
  - click-through flight detail panel;
  - pause/resume, speed control, reset, and scenario regeneration.
- Pytest coverage for config loading, traffic generation, baseline ordering,
  separation enforcement, conflict-risk detection, simulation completion,
  visualization output, live state, REST controls, and WebSocket streaming.

## What is deliberately not implemented yet

- GA optimizer.
- XAI / SHAP explanations.
- OpenAP or XGBoost fuel burn.
- Real ADS-B/OpenSky ingestion. The live dashboard is synthetic and does not
  connect to an external data feed.
- Disruption scenarios.
- Multi-airport or multi-runway operations.
- Gate/taxi optimization.

The fuel number in this milestone is explicitly a **holding-fuel proxy**
(`delay_sec * fuel_flow_proxy`), not a validated fuel model. Do not present it
as OpenAP or XGBoost output.

## Quick start

Use Python 3.12. From this directory:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Run one FCFS case:

```powershell
python -m atdss --strategy fcfs --flights 100 --seed 42 --rate 30
```

Run one wake-priority case:

```powershell
python -m atdss --strategy priority --flights 100 --seed 42 --rate 30
```

Generate the visual simulation:

```powershell
python -m atdss --strategy fcfs --flights 100 --seed 42 --rate 30 --visual
```

Add `--open` to launch it automatically:

```powershell
python -m atdss --strategy fcfs --flights 100 --seed 42 --rate 30 --visual --open
```

The visual simulation is a standalone HTML file. It needs no server and no
additional Python package. Open the generated file in any browser. It shows:

- aircraft moving along a 10 NM final approach in real time;
- wake-category colours;
- the separation gap between aircraft;
- runway occupancy after touchdown;
- the holding queue;
- live landed, on-final, holding, and average-delay counters;
- play/pause, reset, speed, and timeline controls.

A deep link to a point on the timeline is also supported:

```text
results/simulation_fcfs_100.html?t=0.5
```

## Live dashboard

Start the synthetic live simulator with 100 flights, 60 simulated seconds per
wall-clock second, and open the browser automatically:

```powershell
python -m atdss.dashboard --flights 100 --seed 42 --rate 30 --speed 60 --open
```

Or run it without opening a browser:

```powershell
python -m atdss.dashboard --flights 100 --seed 42 --rate 30
```

Then open <http://127.0.0.1:8000>. The dashboard streams a snapshot over a
WebSocket every 0.5 seconds and exposes REST controls:

- `GET /api/state` — complete dashboard snapshot;
- `GET /api/flights` — flight rows;
- `GET /api/metrics` — aggregate metrics;
- `POST /api/control` — pause, resume, toggle, speed, reset, seek, regenerate;
- `POST /api/scenario` — generate a new traffic sample;
- `WS /ws` — live snapshot stream.

Useful CLI options include `--strategy fcfs|priority`, `--host`, `--port`,
`--config`, and `--speed`. The dashboard is also usable as a console script
after installation:

```powershell
atdss-dashboard --flights 100 --open
```

The live dashboard is a synthetic simulator view. It does not ingest ADS-B,
OpenSky, or airport operational data.

Run the full 100/250/500 experiment. Each volume is placed inside the same
12-hour demand window, so the volumes correspond to roughly 8, 21, and 42
arrivals/hour:

```powershell
python -m atdss --compare --counts 100 250 500 --reps 5 --seed 42
```

Override the demand window if needed:

```powershell
python -m atdss --compare --horizon-hours 10
```

Optional time-of-day peak multiplier for a single Poisson run:

```powershell
python -m atdss --strategy fcfs --flights 100 --peak
```

The peak multiplier is not used in `--compare`, because that mode uses a fixed
demand window.

Run tests:

```powershell
python -m pytest -q
```

## Generated artifacts

`python -m atdss --compare` writes to `results/`:

- `baseline_comparison.csv`: one row per strategy, volume, and replication.
- `sample_sequence.csv`: ordered aircraft for the first run of each strategy.
- `summary.md`: aggregate table and metric definitions.
- `fig_delay_vs_traffic.png`: average delay with replication spread.
- `fig_conflict_risk_vs_traffic.png`: conflict-risk pairs.
- `fig_fuel_proxy_vs_traffic.png`: holding-fuel proxy.
- `simulation_<strategy>_<flights>.html`: standalone visual simulation when
  `--visual` is used.

## Layout

```text
atdss-code/
  config/ehamp.yaml       Airport, separation, traffic, and proxy settings
  src/atdss/
    config.py             YAML loading and typed airport config
    models.py             Aircraft, strategy, conflict, and result models
    traffic.py            Poisson traffic and fleet-mix generation
    sequencing.py         FCFS, wake priority, and separation enforcement
    conflict.py           Consecutive-pair conflict-risk analysis
    simulation.py         SimPy single-runway execution
    metrics.py            Delay, throughput, safety, and fuel-proxy metrics
    experiments.py        Replication runner and artifact writer
    plots.py              Matplotlib figures
    visualization.py      Standalone HTML/Canvas animation
    cli.py                Command-line entry point
    dashboard/            Live FastAPI/WebSocket dashboard
      state.py            Live clock, status transitions, snapshots, controls
      app.py              REST API, WebSocket stream, static file serving
      __main__.py         python -m atdss.dashboard entry point
      static/             Vanilla HTML/CSS/Canvas dashboard
  tests/test_pipeline.py  End-to-end and unit checks
  tests/test_visualization.py  Animation payload and HTML checks
  tests/test_dashboard_state.py  Live state and status-transition checks
  tests/test_dashboard_api.py    REST, static-asset, and WebSocket checks
```

## Design note: fixed demand window

The 100/250/500 experiment uses a fixed 12-hour window for every volume. This
means the three cases correspond to increasing demand (about 8, 21, and 42
arrivals/hour), rather than simply running the same traffic rate for longer.
Without a fixed window, a longer run at the same rate can show a lower average
delay because the initial queue is amortized over more aircraft. The fixed
window keeps the comparison interpretable.

The 500-arrival case is near or above the capacity of a single runway with this
fleet mix, so its delay and conflict-risk values are expected to rise sharply.
That is the intended saturation signal, not a model failure.

## Metric definitions

- **Assigned landing time**: the earliest time that satisfies the scheduled
  arrival and the required wake separation after the previous aircraft.
- **Delay**: actual landing time minus scheduled arrival time.
- **Conflict-risk pair**: a consecutive pair whose original scheduled gap was
  below the required wake-separation gap, meaning sequencing had to intervene.
- **Separation violation**: a consecutive pair whose actual landing gap is
  below the required separation. Because the scheduler enforces hard
  separation, this should be zero. A nonzero value is a correctness failure.
- **Tight pair**: actual gap below `conflict_margin_ratio` times the required
  gap (default 1.20).
- **Separation pressure**: delay forced by separation, summed across pairs.
- **Throughput**: landed aircraft divided by the observed arrival horizon.

## Design note: why conflict-risk instead of "conflicts"

If the scheduler always enforces separation, every final sequence has zero
landing-gap violations by construction. Reporting only that number would be
uninformative. This milestone therefore reports both:

1. the hard safety check (violations, expected zero); and
2. the amount of separation pressure and conflict risk present in the
   pre-sequencing schedule.

This distinction should be kept explicit in the report and presentation.

## Git

This directory is intended to be its own repository:

```powershell
git init
git add .
git commit -m "Add AT-DSS simulation milestone"
```

The `.gitignore` excludes the virtual environment, caches, and generated
results. Keep `results/.gitkeep` if you want the output directory to exist in
the repository.
