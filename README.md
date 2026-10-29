# AT-DSS: Arrival Sequencing Simulation and Live Dashboard

AT-DSS (AI-assisted Airport Arrival Sequencing Decision Support) is a research
prototype for arrival sequencing at a single-runway airport. This repository is
the simulation-first implementation slice: it generates synthetic traffic,
applies baseline sequencing and wake-separation rules, simulates runway use,
analyses separation risk, and serves a live synthetic operations dashboard.

The project is a **working baseline and demonstration**, not a production air
traffic control system. The GA optimizer, explainable-AI layer, real flight-data
ingestion, and validated fuel model are not implemented yet.

See [`STATUS.md`](STATUS.md) for the milestone checklist, result snapshot, and a
suggested demo sequence.

## Requirements

- Python **3.12**
- A modern browser with Canvas and WebSocket support
- PowerShell on Windows, or a POSIX shell on macOS/Linux
- No API keys, ADS-B receiver, or external data feed

## Run it

Run every command from the repository root. A fresh clone needs the one-time
setup step first.

### Windows (PowerShell)

One-time setup:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Start the dashboard:

```powershell
.\.venv\Scripts\python.exe -m atdss.dashboard --flights 100 --seed 42 --rate 30 --open
```

By default the scenario plays at **Normal 1× real time**. Use the speed buttons
(or `--speed 5`) only when you want to fast-forward a demo. For a shorter
real-time demo, use `--flights 20`; 100 flights at Normal speed lasts several
hours.

If the `py` launcher is unavailable, create the environment with
`python -m venv .venv`, using Python 3.12 on `PATH`.

### macOS / Linux

One-time setup:

```bash
python3.12 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -e ".[dev]"
```

Start the dashboard:

```bash
./.venv/bin/python -m atdss.dashboard --flights 100 --seed 42 --rate 30 --open
```

If `python3.12` is not available, install Python 3.12 or use the command name
that points to Python 3.12 on your system.

### Dashboard URL

```text
http://127.0.0.1:8000
```

If the browser does not open automatically, open that URL manually. Stop the
server with `Ctrl+C`.

### If you see `No module named 'atdss'`

The package is installed into this repository's `.venv`, not a global Python
installation or another project's environment. Make sure you are in the
repository root and use the explicit interpreter paths above.

To check the active interpreter:

```powershell
# Windows
(Get-Command python).Source
```

```bash
# macOS / Linux
which python
```

Activation is optional but also works:

```powershell
# Windows
.\.venv\Scripts\Activate.ps1
```

```bash
# macOS / Linux
source .venv/bin/activate
```

After activation, `python -m atdss.dashboard` uses the repository environment.

### Command convention

The remaining examples use the Windows interpreter path
`.\.venv\Scripts\python.exe`. On macOS/Linux, replace it with
`./.venv/bin/python`.

## What you should see

The dashboard opens with a **100-flight synthetic scenario** and shows:

- a simulated clock that advances in real time;
- a live airport map for Cochin International Airport (VOCI/COK) with aircraft
  moving from en-route, through the hold, onto final approach, and along the
  runway/taxiway;
- a 10 NM final-approach radar;
- a holding stack on the left;
- runway occupancy and the next landing;
- a sortable flight board with schedule, ETA, actual landing, status, delay, and
  conflict-risk flags;
- a runway timeline with scheduled, assigned, and actual landing markers;
- live alerts and metric cards;
- a flight detail drawer when a row is clicked.

The clock is **elapsed simulated time**, starting at `00:00:00`; it is not real
UTC. The dashboard replays a completed SimPy scenario in simulated time. It does
not step the SimPy event loop in real time.

## Verify the installation

```powershell
# Windows
.\.venv\Scripts\python.exe -m pytest -q
```

```bash
# macOS / Linux
./.venv/bin/python -m pytest -q
```

Expected result:

```text
27 passed
```

A third-party deprecation warning from Starlette/httpx may also appear; it does
not affect the tests.

## At a glance

| Item | Current state |
|---|---|
| Airport | VOCI / Cochin International Airport (COK), Kochi, India — arrival runway 09 |
| Traffic | Synthetic Poisson arrivals with a configurable fleet mix |
| Sequencing | FCFS and bounded wake-priority baselines |
| Safety model | ICAO-style wake-separation matrix |
| Runway model | Single runway with occupancy time |
| Dashboard | FastAPI + WebSocket + vanilla HTML/CSS/Canvas |
| Experiments | 100/250/500 arrivals, 5 replications, fixed 12-hour window |
| Tests | 27 passing |
| Data source | Synthetic only; no ADS-B/OpenSky feed |
| Scope | Approximately 30% of the planned AT-DSS project |

## Live dashboard

Each scenario is generated once by the existing SimPy pipeline. A live state
layer then replays that scenario in simulated time at **1× real time by
default** and updates flight statuses, positions, runway occupancy, alerts, and
metrics. Pressing **Regenerate** runs a new simulation with the selected
parameters.

### Dashboard features

- **Clock and playback:** pause/resume, Normal 1× default, speed buttons, reset.
- **Live airport map:** a real-airport view for VOCI/COK with the runway,
  terminal, localizer path, holding pattern, and moving arrival aircraft.
- **Final-approach radar:** aircraft positions, distance from the threshold,
  runway occupancy, and holding stack.
- **Flight board:** callsign, aircraft type, wake category, origin, scheduled
  time, assigned ETA, actual landing time, status, delay, and risk flag.
- **Runway timeline:** scheduled markers, assigned slots, and actual landings.
- **Alerts:** separation risk, queue build-up, high delay, and runway occupancy.
- **Flight detail drawer:** timing, live position, separation margin,
  predecessor, and holding-fuel proxy.
- **Scenario form:** flights, seed, strategy, and arrival rate.

The map is a schematic local view built around the published VOCI runway
09/27 geometry. It is for simulation and demonstration only, not for
navigation.

### Controls

| Control | Effect |
|---|---|
| Pause / Resume | Stop or restart simulated time |
| Reset | Restart the current scenario from the beginning |
| Speed | Playback rate; `1×` follows real time, higher values fast-forward |
| Regenerate | Generate a new scenario from the form parameters |
| Status filter | Show only scheduled, en-route, holding, final, or landed flights |
| Search | Filter by callsign, aircraft type, origin, or wake category |
| Row click | Open the flight detail drawer |

### Dashboard CLI options

| Option | Default | Description |
|---|---:|---|
| `--config` | repository VOCI config | Path to an airport YAML file |
| `--host` | `127.0.0.1` | Bind address |
| `--port` | `8000` | Bind port |
| `--flights` | `100` | Number of arrival flights |
| `--seed` | `42` | Synthetic traffic seed |
| `--strategy` | `fcfs` | `fcfs` or `priority` |
| `--rate` | `30` | Arrival demand in flights per hour |
| `--speed` | `1` | Playback rate; `1` = real time |
| `--open` | off | Open the dashboard in the default browser |
| `--log-level` | `info` | Uvicorn log level |

The packaged console script is also available after installation:

```powershell
.\.venv\Scripts\atdss-dashboard.exe --flights 100 --open
```

On macOS/Linux use `./.venv/bin/atdss-dashboard`.

### Dashboard API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/state` | Complete dashboard snapshot |
| `GET` | `/api/flights` | Flight rows |
| `GET` | `/api/metrics` | Aggregate metrics |
| `GET` | `/api/health` | Server health and simulation status |
| `POST` | `/api/control` | Pause, resume, toggle, speed, reset, seek, regenerate |
| `POST` | `/api/scenario` | Generate a new traffic sample |
| `WS` | `/ws` | Live snapshot stream, sent every 0.5 seconds |

Interactive API documentation is available at:

```text
http://127.0.0.1:8000/docs
```

Example control requests:

```json
{"action": "pause"}
{"action": "speed", "value": 1}
{"action": "regenerate", "flights": 250, "seed": 7, "strategy": "priority", "rate": 30}
```

Example PowerShell request:

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://127.0.0.1:8000/api/control" `
  -ContentType "application/json" `
  -Body '{"action":"pause"}'
```

The dashboard is synthetic. It does **not** ingest ADS-B, OpenSky, or airport
operational data.

## Batch simulation

Run one FCFS case:

```powershell
.\.venv\Scripts\python.exe -m atdss --strategy fcfs --flights 100 --seed 42 --rate 30
```

Run one bounded wake-priority case:

```powershell
.\.venv\Scripts\python.exe -m atdss --strategy priority --flights 100 --seed 42 --rate 30
```

The bounded priority baseline subtracts a fixed time bonus from the scheduled
time: Heavy 180 s, Medium 60 s, Light 0 s. It is not an “all Heavy first” sort.

Optional time-of-day peak multiplier for a single Poisson run:

```powershell
.\.venv\Scripts\python.exe -m atdss --strategy fcfs --flights 100 --peak
```

The peak multiplier is not used by `--compare`, because that mode uses a fixed
demand window.

## Standalone visual playback

Generate a self-contained HTML animation of one completed run:

```powershell
.\.venv\Scripts\python.exe -m atdss --strategy fcfs --flights 100 --seed 42 --rate 30 --visual
```

Open it automatically:

```powershell
.\.venv\Scripts\python.exe -m atdss --strategy fcfs --flights 100 --seed 42 --rate 30 --visual --open
```

The generated file is:

```text
results/simulation_fcfs_100.html
```

This is a standalone playback of one completed run, not the live dashboard. It
shows aircraft moving along the 10 NM final approach, wake-category colours,
separation gaps, runway occupancy, the arrival queue, and live counters.

**Normal 1×** is selected by default, so the animation follows the synthetic
timeline in real time. A 10 NM final approach takes about 4.3 minutes and runway
occupancy about 40 seconds. Use the faster buttons only for demos. A 100-flight
run at Normal speed lasts several hours; 20–30 flights is more practical for a
real-time demonstration.

Deep link to a point on the timeline:

```text
results/simulation_fcfs_100.html?t=0.5
```

## Traffic-scaling experiment

The experiment uses a fixed 12-hour demand window for every volume. Therefore
100, 250, and 500 arrivals correspond to approximately 8, 21, and 42
arrivals/hour, rather than simply running the same rate for longer.

```powershell
.\.venv\Scripts\python.exe -m atdss --compare --counts 100 250 500 --reps 5 --seed 42
```

Override the demand window:

```powershell
.\.venv\Scripts\python.exe -m atdss --compare --horizon-hours 10
```

### Current result snapshot

Seed 42, five replications, fixed 12-hour window:

| Strategy | Flights | Avg delay (s) | Conflict-risk pairs | Separation violations |
|---|---:|---:|---:|---:|
| FCFS | 100 | 9.7 | 17.0 | 0 |
| FCFS | 250 | 65.6 | 106.8 | 0 |
| FCFS | 500 | 2,253.5 | 327.0 | 0 |
| Priority | 100 | 24.1 | 17.2 | 0 |
| Priority | 250 | 92.3 | 98.0 | 0 |
| Priority | 500 | 2,302.0 | 274.0 | 0 |

The 500-arrival case is near or above single-runway capacity with this fleet
mix. The sharp delay increase is the intended saturation signal, not a model
failure.

## Generated artifacts

The batch tools write to `results/`:

| File | Purpose |
|---|---|
| `baseline_comparison.csv` | One row per strategy, volume, and replication |
| `sample_sequence.csv` | Ordered aircraft for the first run of each strategy |
| `summary.md` | Aggregate table and metric definitions |
| `fig_delay_vs_traffic.png` | Average delay by traffic volume |
| `fig_conflict_risk_vs_traffic.png` | Conflict-risk pairs by traffic volume |
| `fig_fuel_proxy_vs_traffic.png` | Holding-fuel proxy by traffic volume |
| `simulation_<strategy>_<flights>.html` | Standalone visual playback when `--visual` is used |

`results/` is ignored by Git except for `results/.gitkeep`. The live dashboard
does not write result files.

## How it works

```text
config/voci.yaml
        |
        v
synthetic traffic generation
        |
        v
sequencing (FCFS or bounded wake priority)
        |
        v
wake-separation enforcement
        |
        v
SimPy single-runway execution
        |
        +--> conflict analysis + metrics
        |          |
        |          +--> CSV / Markdown / PNG
        |          +--> standalone HTML playback
        |
        +--> live state layer
                   |
                   v
          FastAPI REST + WebSocket
                   |
                   v
             browser dashboard
```

The live state layer derives statuses from the completed sequence:

- scheduled → en route → holding → final → landed;
- final-approach position from the actual landing time and approach speed;
- runway occupancy from the landing time and occupancy duration;
- alerts and metrics for the current simulated time.

## Metrics and interpretation

| Metric | Meaning |
|---|---|
| **Assigned landing time** | Earliest time satisfying the scheduled arrival and required wake separation after the previous aircraft |
| **Delay** | Actual landing time minus scheduled arrival time |
| **Conflict-risk pair** | Consecutive pair whose original scheduled gap was below the required wake-separation gap, meaning sequencing had to intervene |
| **Separation violation** | Consecutive pair whose actual landing gap is below required separation; expected to be zero |
| **Tight pair** | Actual gap below `conflict_margin_ratio` times the required gap (default 1.20) |
| **Separation pressure** | Delay forced by separation, summed across pairs |
| **Throughput** | Landed aircraft divided by the observed arrival horizon |
| **Holding-fuel proxy** | Delay seconds multiplied by a wake-category fuel-flow proxy |

Because the scheduler always enforces separation, every final sequence has zero
landing-gap violations by construction. The conflict-risk metric therefore
measures how often the original schedule was already below the required gap and
needed intervention.

The **fuel number is a holding-fuel proxy**, not an OpenAP or XGBoost result. Do
not present it as a validated fuel model.

## Scope

### Implemented

- Synthetic Poisson traffic with a configurable fleet mix.
- VOCI/Cochin International Airport single-runway configuration with a real
  airport map view.
- FCFS and bounded wake-priority baselines.
- ICAO-style wake-separation enforcement.
- Arbitrary-sequence support for a future optimizer.
- SimPy single-runway execution.
- Consecutive-pair conflict-risk and separation analysis.
- Delay, throughput, safety, and holding-fuel-proxy metrics.
- 100/250/500-arrival experiment with five replications.
- CSV, Markdown, PNG, and standalone HTML outputs.
- Live synthetic dashboard with FastAPI, WebSocket, radar, flight board,
  runway timeline, alerts, detail drawer, and controls.
- Automated tests for the pipeline, visualization, live state, REST API, and
  WebSocket stream.

### Not implemented

- GA sequence optimizer.
- XAI / SHAP explanations.
- OpenAP or XGBoost fuel burn.
- Real ADS-B/OpenSky ingestion.
- Disruption scenarios.
- Multi-airport or multi-runway operations.
- Gate or taxi optimization.

This is not a certified operational system. It is a research and demonstration
prototype using synthetic data.

## Project layout

```text
atdss-code/
  config/voci.yaml                   VOCI/COK airport, map, separation, and proxy settings
  config/ehamp.yaml                  Legacy EHAM comparison configuration
  src/atdss/
    config.py                        YAML loading and typed airport config
    models.py                        Aircraft, strategy, conflict, and result models
    traffic.py                       Synthetic Poisson traffic and fleet mix
    sequencing.py                    FCFS, wake priority, separation enforcement
    conflict.py                      Consecutive-pair conflict-risk analysis
    simulation.py                    SimPy single-runway execution
    metrics.py                       Delay, throughput, safety, and fuel-proxy metrics
    experiments.py                   Replication runner and artifact writer
    plots.py                         Matplotlib figures
    visualization.py                 Standalone HTML/Canvas playback
    cli.py                           Batch command-line entry point
    dashboard/
      state.py                       Live clock, statuses, snapshots, controls
      app.py                         REST API, WebSocket stream, static serving
      __main__.py                    python -m atdss.dashboard entry point
      static/                        HTML, CSS, and Canvas dashboard
  tests/
    test_pipeline.py                 Pipeline and unit checks
    test_visualization.py            Animation payload and HTML checks
    test_dashboard_state.py          Live state and status-transition checks
    test_dashboard_api.py            REST, static-asset, and WebSocket checks
  results/                           Generated artifacts (Git-ignored)
  README.md
  STATUS.md
  pyproject.toml
  requirements.txt
```

## Troubleshooting

### `No module named 'atdss'`

You are not running the repository's virtual environment. From the repository
root, use:

```powershell
.\.venv\Scripts\python.exe -m atdss.dashboard --help
```

Check the interpreter:

```powershell
(Get-Command python).Source
```

### The dashboard does not open automatically

Open the URL manually:

```text
http://127.0.0.1:8000
```

If port 8000 is already in use:

```powershell
.\.venv\Scripts\python.exe -m atdss.dashboard --port 8010 --open
```

### PowerShell blocks `Activate.ps1`

Allow scripts for the current shell only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Or skip activation and use `.\.venv\Scripts\python.exe` directly.

### The dashboard loads but shows no data

- Confirm the server is running on the URL and port you opened.
- Check that the browser is not blocking WebSocket connections.
- Open `http://127.0.0.1:8000/api/health` directly.
- Check the terminal for Uvicorn errors.

### The 500-flight case has very high delay

This is expected. The 500-arrival case is near or above the single-runway
capacity of the configured fleet mix, so queueing and delay rise sharply.

## Documentation and help

- [`STATUS.md`](STATUS.md) — milestone status, results snapshot, and demo plan.
- `http://127.0.0.1:8000/docs` — interactive dashboard API documentation.
- `.\.venv\Scripts\python.exe -m atdss --help` — batch simulation options.
- `.\.venv\Scripts\python.exe -m atdss.dashboard --help` — dashboard options.

## Repository notes

The repository is already initialized. The `.gitignore` excludes `.venv/`,
caches, build output, and generated files under `results/`; `results/.gitkeep` is
tracked so the directory exists in a fresh checkout.
