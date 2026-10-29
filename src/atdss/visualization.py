"""Standalone HTML animation for a simulated arrival sequence.

The generated file is self-contained: it embeds the simulation result as JSON
and renders a top-down final-approach view on an HTML canvas. It does not need
Streamlit, a web server, or an internet connection.
"""

from __future__ import annotations

import html
import json
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import AirportConfig, WakeCategory
from .models import SimulationResult


def build_visual_payload(
    config: AirportConfig, result: SimulationResult
) -> dict[str, Any]:
    """Build the JSON payload consumed by the HTML/JS animation."""
    speed_nm_per_sec = config.approach_speed_nm_per_sec
    final_approach_duration_sec = config.faf_distance_nm / speed_nm_per_sec

    aircraft: list[dict[str, Any]] = []
    for item in result.sequence:
        actual = (
            item.actual_landing_sec
            if item.actual_landing_sec is not None
            else item.assigned_or_scheduled_sec
        )
        aircraft.append(
            {
                "id": item.id,
                "callsign": item.callsign,
                "type": item.icao_type,
                "wake": item.wake.value,
                "scheduled": round(item.scheduled_arrival_sec, 3),
                "assigned": round(item.assigned_or_scheduled_sec, 3),
                "actual": round(actual, 3),
                "delay": round(item.delay_sec, 3),
                "fuel": round(item.fuel_proxy_kg, 3),
            }
        )

    actual_times = [item["actual"] for item in aircraft]
    animation_start = max(0.0, min(actual_times) - final_approach_duration_sec - 30.0)
    animation_end = max(actual_times) + config.runway_occupancy_sec + 90.0

    separation = {
        leading.value: {
            following.value: float(value)
            for following, value in followers.items()
        }
        for leading, followers in config.separation_nm.items()
    }

    return {
        "airport": {"icao": config.icao, "name": config.name},
        "strategy": result.strategy,
        "metrics": result.metrics,
        "runway": {
            "id": config.arrival_runway,
            "occupancy_sec": float(config.runway_occupancy_sec),
            "faf_distance_nm": float(config.faf_distance_nm),
            "approach_speed_kts": float(config.final_approach_speed_kts),
            "approach_speed_nm_per_sec": float(speed_nm_per_sec),
            "final_approach_duration_sec": float(final_approach_duration_sec),
        },
        "separation_nm": separation,
        "aircraft": aircraft,
        "animation_start_sec": animation_start,
        "animation_end_sec": animation_end,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


def render_html(payload: dict[str, Any], title: str | None = None) -> str:
    """Render a self-contained HTML animation from a payload."""
    airport = payload["airport"]
    strategy = str(payload["strategy"]).upper()
    page_title = title or (
        f"AT-DSS arrival animation - {airport['icao']} - {strategy}"
    )
    data_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    return (
        _HTML_TEMPLATE.replace("__PAGE_TITLE__", html.escape(page_title))
        .replace("__DATA_JSON__", data_json)
        .replace("__GENERATED_AT__", html.escape(str(payload["generated_at"])))
    )


def write_visualization(
    config: AirportConfig,
    result: SimulationResult,
    output_path: str | Path,
    title: str | None = None,
    open_browser: bool = False,
) -> Path:
    """Write the standalone animation and optionally open it in a browser."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_visual_payload(config, result)
    path.write_text(render_html(payload, title=title), encoding="utf-8")
    if open_browser:
        webbrowser.open(path.resolve().as_uri())
    return path


_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__PAGE_TITLE__</title>
<style>
  :root {
    --bg: #08111f;
    --panel: #101d31;
    --panel-2: #14253d;
    --line: #25405f;
    --text: #e6eef9;
    --muted: #8fa8c4;
    --accent: #4cc9f0;
    --heavy: #ff6b6b;
    --medium: #4cc9f0;
    --light: #90be6d;
    --warn: #ffd166;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: radial-gradient(circle at 20% 0%, #102441 0%, var(--bg) 48%);
    color: var(--text);
    font-family: "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }
  .wrap { max-width: 1380px; margin: 0 auto; padding: 22px; }
  header { display: flex; justify-content: space-between; gap: 18px; align-items: flex-end; }
  h1 { font-size: 24px; margin: 0 0 4px; letter-spacing: .2px; }
  .sub { color: var(--muted); font-size: 13px; }
  .badge {
    border: 1px solid var(--line); background: var(--panel); color: var(--accent);
    padding: 8px 12px; border-radius: 999px; font-size: 12px; font-weight: 700;
    letter-spacing: .8px; text-transform: uppercase;
  }
  .stats {
    display: grid; grid-template-columns: repeat(6, minmax(0, 1fr));
    gap: 10px; margin: 18px 0 14px;
  }
  .stat {
    background: linear-gradient(180deg, var(--panel), #0d1929);
    border: 1px solid var(--line); border-radius: 12px; padding: 10px 12px;
  }
  .stat .k { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .7px; }
  .stat .v { font-size: 20px; font-weight: 700; margin-top: 3px; font-variant-numeric: tabular-nums; }
  .main { display: grid; grid-template-columns: minmax(0, 1fr) 300px; gap: 14px; }
  .canvas-card, .side {
    background: linear-gradient(180deg, var(--panel), #0c1727);
    border: 1px solid var(--line); border-radius: 14px;
    box-shadow: 0 18px 50px rgba(0,0,0,.25);
  }
  .canvas-card { padding: 12px; }
  canvas { width: 100%; height: 520px; display: block; border-radius: 10px; background: #0a1424; }
  .controls {
    display: flex; gap: 10px; align-items: center; flex-wrap: wrap;
    margin-top: 10px; padding: 4px 2px 2px;
  }
  button {
    border: 1px solid var(--line); background: var(--panel-2); color: var(--text);
    border-radius: 9px; padding: 9px 14px; font-weight: 700; cursor: pointer;
  }
  button:hover { border-color: var(--accent); }
  button.primary { background: #123a52; border-color: #2d6b8d; color: #dff7ff; }
  input[type="range"] { accent-color: var(--accent); }
  .control-label { color: var(--muted); font-size: 12px; }
  .speed-value { color: var(--text); font-variant-numeric: tabular-nums; min-width: 68px; }
  .scrub { flex: 1; min-width: 180px; }
  .side { padding: 14px; }
  .side h2 { font-size: 13px; text-transform: uppercase; letter-spacing: .8px; color: var(--accent); margin: 0 0 10px; }
  .queue { display: flex; flex-direction: column; gap: 7px; min-height: 210px; }
  .queue-item {
    display: grid; grid-template-columns: 10px 1fr auto; gap: 8px; align-items: center;
    background: #0b1728; border: 1px solid #1c3452; border-radius: 9px; padding: 7px 8px;
  }
  .dot { width: 9px; height: 9px; border-radius: 50%; }
  .callsign { font-size: 12px; font-weight: 700; }
  .meta { color: var(--muted); font-size: 11px; }
  .delay { color: var(--warn); font-size: 11px; font-variant-numeric: tabular-nums; }
  .empty { color: var(--muted); font-size: 12px; padding: 10px 2px; }
  .legend { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 12px; color: var(--muted); font-size: 11px; }
  .legend span { display: inline-flex; align-items: center; gap: 5px; }
  .legend i { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
  .note { color: var(--muted); font-size: 11px; line-height: 1.5; margin-top: 12px; }
  .generated { color: #5f7896; font-size: 10px; margin-top: 10px; }
  @media (max-width: 980px) {
    .stats { grid-template-columns: repeat(3, minmax(0, 1fr)); }
    .main { grid-template-columns: 1fr; }
    canvas { height: 430px; }
  }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div>
      <h1>AT-DSS Arrival Simulation</h1>
      <div class="sub" id="route"></div>
    </div>
    <div class="badge" id="strategy"></div>
  </header>

  <div class="stats">
    <div class="stat"><div class="k">Simulated time</div><div class="v" id="clock">00:00:00</div></div>
    <div class="stat"><div class="k">Landed</div><div class="v" id="landed">0</div></div>
    <div class="stat"><div class="k">On final</div><div class="v" id="onfinal">0</div></div>
    <div class="stat"><div class="k">Holding</div><div class="v" id="holding">0</div></div>
    <div class="stat"><div class="k">Avg delay</div><div class="v" id="avgdelay">0 s</div></div>
    <div class="stat"><div class="k">Separation violations</div><div class="v" id="violations">0</div></div>
  </div>

  <div class="main">
    <section class="canvas-card">
      <canvas id="scene"></canvas>
      <div class="controls">
        <button class="primary" id="play"></button>
        <button id="reset">Reset</button>
        <label class="control-label" for="speed">Speed</label>
        <input id="speed" type="range" min="30" max="1800" step="30" value="120">
        <span class="speed-value" id="speedLabel">120x</span>
        <input id="scrub" class="scrub" type="range" min="0" max="1000" value="0">
      </div>
      <div class="legend">
        <span><i style="background:var(--heavy)"></i>Heavy</span>
        <span><i style="background:var(--medium)"></i>Medium</span>
        <span><i style="background:var(--light)"></i>Light</span>
        <span><i style="background:var(--warn)"></i>Landed / runway</span>
      </div>
    </section>

    <aside class="side">
      <h2>Holding queue</h2>
      <div class="queue" id="queue"></div>
      <h2 style="margin-top:18px">Run facts</h2>
      <div class="note" id="facts"></div>
      <div class="note">
        Aircraft move along a 10 NM final approach at the configured approach
        speed. The horizontal gap between aircraft reflects the wake-separation
        requirement. Holding aircraft are waiting for their assigned landing slot.
      </div>
      <div class="generated">Generated __GENERATED_AT__</div>
    </aside>
  </div>
</div>

<script>
const DATA = __DATA_JSON__;
const A = DATA.aircraft;
const R = DATA.runway;
const COLORS = { H: "#ff6b6b", M: "#4cc9f0", L: "#90be6d" };
const START = DATA.animation_start_sec;
const END = DATA.animation_end_sec;
const DURATION = Math.max(1, END - START);
const FINAL = R.final_approach_duration_sec;
const SPEED_NM_S = R.approach_speed_nm_per_sec;
const OCC = R.occupancy_sec;

const canvas = document.getElementById("scene");
const ctx = canvas.getContext("2d");
const playButton = document.getElementById("play");
const resetButton = document.getElementById("reset");
const speedInput = document.getElementById("speed");
const speedLabel = document.getElementById("speedLabel");
const scrub = document.getElementById("scrub");
const clockEl = document.getElementById("clock");
const landedEl = document.getElementById("landed");
const onfinalEl = document.getElementById("onfinal");
const holdingEl = document.getElementById("holding");
const avgdelayEl = document.getElementById("avgdelay");
const violationsEl = document.getElementById("violations");
const queueEl = document.getElementById("queue");
const factsEl = document.getElementById("facts");

let simTime = START;
let playing = true;
let speed = Number(speedInput.value);
let lastFrame = performance.now();
let lastSidebarUpdate = 0;
let canvasW = 0, canvasH = 0;
let scrubbing = false;

// Optional deep link to a point on the timeline: simulation.html?t=0.5
const params = new URLSearchParams(window.location.search);
if (params.has("t")) {
  const fraction = Math.max(0, Math.min(1, Number(params.get("t")) || 0));
  simTime = START + fraction * DURATION;
  playing = false;
}

document.getElementById("route").textContent =
  DATA.airport.name + " (" + DATA.airport.icao + ")  |  single runway  |  " +
  A.length + " arrivals  |  " + R.faf_distance_nm.toFixed(1) + " NM final";
document.getElementById("strategy").textContent = DATA.strategy.toUpperCase() + " baseline";
document.getElementById("facts").textContent =
  "Approach speed: " + R.approach_speed_kts.toFixed(0) + " kt. " +
  "Final approach time: " + FINAL.toFixed(0) + " s. " +
  "Runway occupancy: " + OCC.toFixed(0) + " s.";

function sizeCanvas() {
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvasW = rect.width;
  canvasH = rect.height;
  canvas.width = Math.round(rect.width * dpr);
  canvas.height = Math.round(rect.height * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}
window.addEventListener("resize", () => { sizeCanvas(); draw(); });

function fmtTime(seconds) {
  const s = Math.max(0, Math.floor(seconds));
  const hh = String(Math.floor(s / 3600)).padStart(2, "0");
  const mm = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
  const ss = String(s % 60).padStart(2, "0");
  return hh + ":" + mm + ":" + ss;
}

function drawRoundRect(x, y, w, h, r) {
  const rr = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + rr, y);
  ctx.arcTo(x + w, y, x + w, y + h, rr);
  ctx.arcTo(x + w, y + h, x, y + h, rr);
  ctx.arcTo(x, y + h, x, y, rr);
  ctx.arcTo(x, y, x + w, y, rr);
  ctx.closePath();
}

function drawScene() {
  if (!canvasW || !canvasH) return;
  ctx.clearRect(0, 0, canvasW, canvasH);

  const pathX0 = canvasW * 0.075;
  const pathX1 = canvasW * 0.79;
  const runwayX0 = canvasW * 0.805;
  const runwayX1 = canvasW * 0.965;
  const pathY = canvasH * 0.58;
  const runwayH = Math.max(34, canvasH * 0.075);

  // Background grid.
  ctx.strokeStyle = "rgba(37,64,95,0.28)";
  ctx.lineWidth = 1;
  for (let x = 0; x < canvasW; x += 48) {
    ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, canvasH); ctx.stroke();
  }
  for (let y = 0; y < canvasH; y += 48) {
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(canvasW, y); ctx.stroke();
  }

  // Final approach centerline.
  ctx.strokeStyle = "rgba(76,201,240,0.55)";
  ctx.lineWidth = 2;
  ctx.setLineDash([10, 8]);
  ctx.beginPath(); ctx.moveTo(pathX0, pathY); ctx.lineTo(pathX1, pathY); ctx.stroke();
  ctx.setLineDash([]);

  // Distance ticks.
  ctx.font = "11px Consolas, monospace";
  ctx.textAlign = "center";
  for (let nm = 0; nm <= R.faf_distance_nm; nm += 2) {
    const x = pathX0 + (1 - nm / R.faf_distance_nm) * (pathX1 - pathX0);
    ctx.strokeStyle = "rgba(143,168,196,0.45)";
    ctx.beginPath(); ctx.moveTo(x, pathY - 13); ctx.lineTo(x, pathY + 13); ctx.stroke();
    if (nm > 0) {
      ctx.fillStyle = "#8fa8c4";
      ctx.fillText(nm + " NM", x, pathY + 32);
    }
  }

  // Runway.
  const runwayY = pathY - runwayH / 2;
  ctx.fillStyle = "#26364d";
  drawRoundRect(runwayX0, runwayY, runwayX1 - runwayX0, runwayH, 6);
  ctx.fill();
  ctx.strokeStyle = "#5d7897";
  ctx.lineWidth = 2;
  ctx.stroke();
  ctx.strokeStyle = "rgba(255,255,255,0.55)";
  ctx.setLineDash([16, 14]);
  ctx.beginPath();
  ctx.moveTo(runwayX0 + 10, pathY);
  ctx.lineTo(runwayX1 - 10, pathY);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = "#c9d8ea";
  ctx.font = "bold 12px Consolas, monospace";
  ctx.textAlign = "center";
  ctx.fillText("RWY " + R.id, (runwayX0 + runwayX1) / 2, pathY - runwayH / 2 - 10);
  ctx.fillStyle = "#8fa8c4";
  ctx.font = "11px Consolas, monospace";
  ctx.fillText("THRESHOLD", runwayX0, pathY + runwayH / 2 + 20);

  // Landed aircraft on runway (fade over occupancy).
  for (const ac of A) {
    const age = simTime - ac.actual;
    if (age >= 0 && age <= OCC) {
      const alpha = 1 - age / OCC;
      ctx.globalAlpha = Math.max(0.15, alpha);
      ctx.fillStyle = "#ffd166";
      ctx.beginPath();
      ctx.arc((runwayX0 + runwayX1) / 2, pathY, 9, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = "#08111f";
      ctx.font = "bold 9px Consolas, monospace";
      ctx.textAlign = "center";
      ctx.fillText("LANDED", (runwayX0 + runwayX1) / 2, pathY + 3);
      ctx.globalAlpha = 1;
    }
  }

  // Aircraft on final approach.
  let onFinal = 0;
  for (const ac of A) {
    const lead = ac.actual - simTime;
    if (lead <= 0 || lead > FINAL) continue;
    onFinal += 1;
    const dist = lead * SPEED_NM_S;
    const x = pathX0 + (1 - dist / R.faf_distance_nm) * (pathX1 - pathX0);
    const color = COLORS[ac.wake] || "#ffffff";
    const y = pathY;

    // Separation halo.
    ctx.beginPath();
    ctx.fillStyle = color + "22";
    ctx.arc(x, y, 17, 0, Math.PI * 2);
    ctx.fill();

    // Aircraft marker.
    ctx.beginPath();
    ctx.fillStyle = color;
    ctx.arc(x, y, 7, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = "#08111f";
    ctx.lineWidth = 2;
    ctx.stroke();

    // Label.
    const label = ac.callsign + "  " + ac.wake;
    ctx.font = "bold 11px Consolas, monospace";
    const tw = ctx.measureText(label).width;
    const bx = Math.max(4, Math.min(canvasW - tw - 18, x - tw / 2 - 8));
    const by = y - 38;
    ctx.fillStyle = "rgba(8,17,31,0.86)";
    drawRoundRect(bx, by, tw + 16, 20, 5);
    ctx.fill();
    ctx.fillStyle = color;
    ctx.textAlign = "left";
    ctx.fillText(label, bx + 8, by + 14);

    // Small delay tag.
    if (ac.delay > 1) {
      ctx.fillStyle = "#ffd166";
      ctx.font = "10px Consolas, monospace";
      ctx.textAlign = "center";
      ctx.fillText("+" + Math.round(ac.delay) + "s", x, y + 27);
    }
  }

  // Time/progress inside canvas.
  ctx.fillStyle = "rgba(8,17,31,0.78)";
  drawRoundRect(12, 12, 170, 44, 7);
  ctx.fill();
  ctx.fillStyle = "#8fa8c4";
  ctx.font = "10px Consolas, monospace";
  ctx.textAlign = "left";
  ctx.fillText("SIMULATED TIME", 22, 28);
  ctx.fillStyle = "#e6eef9";
  ctx.font = "bold 16px Consolas, monospace";
  ctx.fillText(fmtTime(simTime), 22, 47);

  return onFinal;
}

function updateStats(onFinal) {
  const landed = A.filter(a => a.actual <= simTime).length;
  const holding = A.filter(a => a.actual > simTime && simTime < a.actual - FINAL).length;
  const landedDelays = A.filter(a => a.actual <= simTime).map(a => a.delay);
  const avgDelay = landedDelays.length
    ? landedDelays.reduce((s, v) => s + v, 0) / landedDelays.length
    : 0;
  clockEl.textContent = fmtTime(simTime);
  landedEl.textContent = String(landed);
  onfinalEl.textContent = String(onFinal);
  holdingEl.textContent = String(holding);
  avgdelayEl.textContent = Math.round(avgDelay) + " s";
  violationsEl.textContent = String(DATA.metrics.separation_violations || 0);
  return { landed, holding, avgDelay };
}

function updateQueue() {
  const pending = A
    .filter(a => a.actual > simTime && simTime < a.actual - FINAL)
    .sort((a, b) => a.actual - b.actual)
    .slice(0, 8);
  if (!pending.length) {
    queueEl.innerHTML = '<div class="empty">No aircraft waiting.</div>';
    return;
  }
  queueEl.innerHTML = pending.map(a => {
    const color = COLORS[a.wake] || "#ffffff";
    return '<div class="queue-item">' +
      '<span class="dot" style="background:' + color + '"></span>' +
      '<div><div class="callsign">' + a.callsign + '</div>' +
      '<div class="meta">' + a.type + ' - ' + a.wake + ' - ETA ' + fmtTime(a.actual) + '</div></div>' +
      '<div class="delay">+' + Math.round(a.delay) + 's</div>' +
      '</div>';
  }).join("");
}

function syncScrub() {
  if (!scrubbing) {
    scrub.value = String(Math.round(((simTime - START) / DURATION) * 1000));
  }
}

function frame(now) {
  const dt = Math.min(0.1, (now - lastFrame) / 1000);
  lastFrame = now;
  if (playing && !scrubbing) {
    simTime += dt * speed;
    if (simTime >= END) {
      simTime = END;
      playing = false;
      playButton.textContent = "Play";
    }
  }
  const onFinal = drawScene() || 0;
  updateStats(onFinal);
  if (now - lastSidebarUpdate > 150) {
    updateQueue();
    lastSidebarUpdate = now;
  }
  syncScrub();
  requestAnimationFrame(frame);
}

playButton.addEventListener("click", () => {
  if (simTime >= END) simTime = START;
  playing = !playing;
  playButton.textContent = playing ? "Pause" : "Play";
});
resetButton.addEventListener("click", () => {
  simTime = START;
  playing = false;
  playButton.textContent = "Play";
  drawScene();
  updateQueue();
});
speedInput.addEventListener("input", () => {
  speed = Number(speedInput.value);
  speedLabel.textContent = speed + "x";
});
scrub.addEventListener("input", () => {
  scrubbing = true;
  simTime = START + (Number(scrub.value) / 1000) * DURATION;
  playing = false;
  playButton.textContent = "Play";
  drawScene();
  updateQueue();
});
scrub.addEventListener("change", () => { scrubbing = false; });

playButton.textContent = playing ? "Pause" : "Play";
sizeCanvas();
drawScene();
updateQueue();
requestAnimationFrame(frame);
</script>
</body>
</html>
"""
