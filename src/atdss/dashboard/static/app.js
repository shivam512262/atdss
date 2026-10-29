"use strict";

const $ = (id) => document.getElementById(id);

const STATUS = {
  scheduled: { label: "Scheduled", color: "#8da4b8" },
  en_route: { label: "En route", color: "#5c9dff" },
  holding: { label: "Holding", color: "#f4a261" },
  final: { label: "Final", color: "#2ec4b6" },
  landed: { label: "Landed", color: "#7bd389" },
};

const SPEEDS = [1, 5, 10, 30, 60, 120, 240, 600];

let snapshot = null;
let receivedAt = 0;
let selectedId = null;
let sortKey = "sequence_position";
let sortDir = 1;
let filterStatus = "all";
let searchText = "";
let formInitialized = false;
let socket = null;
let reconnectTimer = null;
let toastTimer = null;

function fmtClock(seconds) {
  const total = Math.max(0, Math.floor(Number(seconds) || 0));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function fmtDelay(seconds) {
  const value = Math.max(0, Math.round(Number(seconds) || 0));
  if (value < 60) return `${value}s`;
  const minutes = Math.floor(value / 60);
  const rest = value % 60;
  return rest ? `${minutes}m ${rest}s` : `${minutes}m`;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));
}

function statusInfo(status) {
  return STATUS[status] || STATUS.scheduled;
}

function displayTime() {
  if (!snapshot) return 0;
  if (snapshot.paused) return snapshot.sim_time;
  const elapsed = Math.min(1.0, Math.max(0, (performance.now() - receivedAt) / 1000));
  return Math.min(snapshot.scenario.end_time, snapshot.sim_time + elapsed * snapshot.speed);
}

function statusAt(flight, t) {
  if (!snapshot) return flight.status;
  if (t >= flight.actual) return "landed";
  if (t >= flight.actual - snapshot.final_approach.duration_sec) return "final";
  if (t >= flight.scheduled - snapshot.final_approach.holding_lead_sec) return "holding";
  if (t >= flight.scheduled - snapshot.final_approach.en_route_lead_sec) return "en_route";
  return "scheduled";
}

function positionAt(flight, t) {
  const status = statusAt(flight, t);
  if (status === "landed") return 0;
  if (status !== "final" || !snapshot) return null;
  const distance = (flight.actual - t) * snapshot.final_approach.speed_nm_per_sec;
  return Math.max(0, Math.min(snapshot.final_approach.faf_distance_nm, distance));
}

function applySnapshot(data) {
  snapshot = data;
  receivedAt = performance.now();

  if (selectedId && !snapshot.flights.some((flight) => flight.id === selectedId)) {
    selectedId = null;
  }

  syncForm();
  render();
}

function syncForm() {
  if (!snapshot) return;
  const form = $("scenarioForm");
  const active = document.activeElement;
  if (formInitialized && form.contains(active)) return;

  const speedSelect = $("speedSelect");
  const speed = Number(snapshot.scenario.speed);
  if (![...speedSelect.options].some((option) => Number(option.value) === speed)) {
    const option = document.createElement("option");
    option.value = String(speed);
    option.textContent = `${speed}×`;
    speedSelect.append(option);
  }
  if (active !== speedSelect) speedSelect.value = String(speed);

  if (!formInitialized) {
    $("flightsInput").value = snapshot.scenario.flights;
    $("seedInput").value = snapshot.scenario.seed;
    $("strategySelect").value = snapshot.scenario.strategy;
    $("rateInput").value = snapshot.scenario.rate;
    formInitialized = true;
  }
}

function setConnection(text, tone) {
  const element = $("connection");
  element.textContent = text;
  element.className = `connection ${tone || ""}`.trim();
}

/* ------------------------------- rendering ------------------------------- */

function render() {
  if (!snapshot) return;

  const metrics = snapshot.metrics;
  $("airportName").textContent =
    `${snapshot.airport.icao} · ${snapshot.airport.name} · RWY ${snapshot.airport.runway}`;
  $("pauseBtn").textContent = snapshot.paused ? "Resume" : "Pause";
  $("pauseBtn").classList.toggle("paused", snapshot.paused);

  $("statLanded").textContent = metrics.landed;
  $("statTotal").textContent = `of ${metrics.total_flights} flights`;
  $("statFinal").textContent = metrics.final;
  $("statRunway").textContent =
    snapshot.runway.status === "occupied"
      ? `RWY ${snapshot.runway.id} occupied`
      : `RWY ${snapshot.runway.id} free`;
  $("statHolding").textContent = metrics.holding;
  $("statEnRoute").textContent = metrics.en_route;
  $("statScheduled").textContent = `${metrics.scheduled} scheduled`;
  $("statDelay").textContent = fmtDelay(metrics.avg_delay_sec);
  $("statRisk").textContent = metrics.conflict_risk_pairs;
  $("statViolations").textContent = `${metrics.separation_violations} separation violations`;

  const runwayPill = $("runwayStatus");
  runwayPill.textContent =
    snapshot.runway.status === "occupied"
      ? `RWY ${snapshot.runway.id} · OCCUPIED`
      : `RWY ${snapshot.runway.id} · FREE`;
  runwayPill.className = `pill ${snapshot.runway.status}`;

  $("alertCount").textContent = String(snapshot.alerts.length);
  renderAlerts();
  renderBoard();
  renderDetail();
  drawTimeline();
}

function renderAlerts() {
  const container = $("alerts");
  if (!snapshot.alerts.length) {
    container.innerHTML =
      '<div class="alert-empty">No active alerts.<br>Separation and queue state nominal.</div>';
    return;
  }
  container.innerHTML = snapshot.alerts
    .map(
      (alert) => `
      <div class="alert ${escapeHtml(alert.severity)}">
        <strong>${escapeHtml(alert.title)}</strong>
        <p>${escapeHtml(alert.message)}</p>
      </div>`
    )
    .join("");
}

function filteredFlights() {
  const query = searchText.trim().toLowerCase();
  const flights = snapshot.flights.filter((flight) => {
    if (filterStatus !== "all" && flight.status !== filterStatus) return false;
    if (!query) return true;
    return [flight.callsign, flight.flight_number, flight.type, flight.origin, flight.wake]
      .some((value) => String(value ?? "").toLowerCase().includes(query));
  });

  flights.sort((a, b) => {
    let left = a[sortKey];
    let right = b[sortKey];
    if (sortKey === "conflict_risk") {
      left = left ? 1 : 0;
      right = right ? 1 : 0;
    }
    if (typeof left === "string" || typeof right === "string") {
      return String(left ?? "").localeCompare(String(right ?? "")) * sortDir;
    }
    return ((Number(left) || 0) - (Number(right) || 0)) * sortDir;
  });
  return flights;
}

function renderBoard() {
  if (!snapshot) return;
  const flights = filteredFlights();
  $("boardSummary").textContent =
    `${flights.length} of ${snapshot.metrics.total_flights} flights shown · ` +
    `${snapshot.scenario.strategy.toUpperCase()} sequencing`;

  updateSortIndicators();

  if (!flights.length) {
    $("flightBody").innerHTML =
      '<tr><td colspan="11" class="alert-empty">No flights match the current filter.</td></tr>';
    return;
  }

  $("flightBody").innerHTML = flights.map(flightRow).join("");
}

function flightRow(flight) {
  const meta = statusInfo(flight.status);
  const selected = flight.id === selectedId ? " selected" : "";
  const landed = flight.status === "landed" ? " landed" : "";
  const actual = flight.status === "landed" ? fmtClock(flight.actual) : "—";
  const margin = flight.separation_margin_sec;
  const risk = flight.conflict_risk
    ? `<span class="risk-flag" title="Margin ${margin == null ? "n/a" : `${margin.toFixed(1)} s`}">RISK</span>`
    : '<span class="muted">—</span>';
  const delayClass = flight.delay > 0 ? "delay-late" : "delay-ok";
  const delayText = flight.delay > 0 ? `+${fmtDelay(flight.delay)}` : "0";

  return `
    <tr data-id="${escapeHtml(flight.id)}" class="${selected}${landed}">
      <td class="num muted">${flight.sequence_position + 1}</td>
      <td>
        <div class="flight-cell">
          <span class="status-dot" style="background:${meta.color}"></span>
          <strong>${escapeHtml(flight.callsign)}</strong>
        </div>
      </td>
      <td>${escapeHtml(flight.type)}</td>
      <td><span class="wake wake-${escapeHtml(flight.wake)}">${escapeHtml(flight.wake)}</span></td>
      <td class="mono">${escapeHtml(flight.origin)}</td>
      <td class="mono">${fmtClock(flight.scheduled)}</td>
      <td class="mono">${fmtClock(flight.eta)}</td>
      <td class="mono">${actual}</td>
      <td><span class="badge status-${escapeHtml(flight.status)}">${meta.label}</span></td>
      <td class="num ${delayClass}">${delayText}</td>
      <td class="num">${risk}</td>
    </tr>`;
}

function updateSortIndicators() {
  document.querySelectorAll("th[data-sort]").forEach((header) => {
    header.classList.remove("sort-asc", "sort-desc");
    if (header.dataset.sort === sortKey) {
      header.classList.add(sortDir > 0 ? "sort-asc" : "sort-desc");
    }
  });
}

function renderDetail() {
  const panel = $("detailPanel");
  const title = $("detailTitle");
  const body = $("detailBody");
  const flight = snapshot ? snapshot.flights.find((item) => item.id === selectedId) : null;

  if (!flight) {
    panel.classList.remove("open");
    title.textContent = "Select a flight";
    body.innerHTML =
      '<p class="muted">Click any row in the flight board to inspect schedule, separation, and live position.</p>';
    return;
  }

  panel.classList.add("open");
  const meta = statusInfo(flight.status);
  title.textContent = flight.callsign;
  const predecessor = flight.predecessor_id
    ? snapshot.flights.find((item) => item.id === flight.predecessor_id)
    : null;
  const position = flight.position_nm;
  const margin = flight.separation_margin_sec;

  let note;
  let noteClass = "";
  if (flight.status === "final") {
    note = `On final approach ${position == null ? "" : `at ${position.toFixed(2)} NM`} from the threshold.`;
    noteClass = "ok";
  } else if (flight.status === "holding") {
    note = "Holding in the arrival stack, awaiting its assigned landing slot.";
  } else if (flight.status === "landed") {
    note = `Landed at ${fmtClock(flight.actual)}; actual delay ${fmtDelay(flight.delay)}.`;
    noteClass = "ok";
  } else if (flight.status === "en_route") {
    note = "En route to the terminal area. Scheduled to enter the arrival stream shortly.";
    noteClass = "ok";
  } else {
    note = "Scheduled arrival outside the current 30-minute planning horizon.";
    noteClass = "ok";
  }
  if (flight.conflict_risk) {
    note += " The pre-sequencing gap was below the required wake separation; the scheduler inserted an intervention.";
  }

  body.innerHTML = `
    <div class="detail-grid">
      <div class="detail-item"><span>Status</span><strong><span class="badge status-${escapeHtml(flight.status)}">${meta.label}</span></strong></div>
      <div class="detail-item"><span>Sequence</span><strong>#${flight.sequence_position + 1} of ${snapshot.metrics.total_flights}</strong></div>
      <div class="detail-item"><span>Type / wake</span><strong>${escapeHtml(flight.type)} · ${escapeHtml(flight.wake)}</strong></div>
      <div class="detail-item"><span>Origin</span><strong>${escapeHtml(flight.origin)}</strong></div>
      <div class="detail-item"><span>Scheduled</span><strong>${fmtClock(flight.scheduled)}</strong></div>
      <div class="detail-item"><span>Assigned ETA</span><strong>${fmtClock(flight.eta)}</strong></div>
      <div class="detail-item"><span>Actual landing</span><strong>${flight.status === "landed" ? fmtClock(flight.actual) : "—"}</strong></div>
      <div class="detail-item"><span>Delay</span><strong>${flight.delay > 0 ? `+${fmtDelay(flight.delay)}` : "0"}</strong></div>
      <div class="detail-item"><span>Position</span><strong>${position == null ? "—" : `${position.toFixed(2)} NM`}</strong></div>
      <div class="detail-item"><span>Holding-fuel proxy</span><strong>${flight.fuel_proxy_kg.toFixed(1)} kg</strong></div>
      <div class="detail-item"><span>Separation margin</span><strong>${margin == null ? "—" : `${margin.toFixed(1)} s`}</strong></div>
      <div class="detail-item"><span>Predecessor</span><strong>${predecessor ? escapeHtml(predecessor.callsign) : "—"}</strong></div>
    </div>

    <div class="detail-note ${noteClass}">${escapeHtml(note)}</div>

    <div class="detail-section">
      <h3>Runway</h3>
      <div class="detail-grid">
        <div class="detail-item"><span>Arrival runway</span><strong>${escapeHtml(flight.runway)}</strong></div>
        <div class="detail-item"><span>Occupancy</span><strong>${snapshot.runway.occupancy_sec.toFixed(0)} s</strong></div>
      </div>
    </div>

    <p class="muted" style="margin-top:18px;font-size:0.72rem;">
      Fuel is a delay-based holding proxy, not an OpenAP or XGBoost model output.
      Separation risk compares the unsequenced schedule with the wake-separation requirement.
    </p>`;
}

/* -------------------------------- radar --------------------------------- */

function resizeCanvas(canvas) {
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  const width = Math.max(1, Math.floor(rect.width * dpr));
  const height = Math.max(1, Math.floor(rect.height * dpr));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, w: rect.width, h: rect.height };
}

function roundRect(ctx, x, y, width, height, radius) {
  const r = Math.min(radius, width / 2, height / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + width, y, x + width, y + height, r);
  ctx.arcTo(x + width, y + height, x, y + height, r);
  ctx.arcTo(x, y + height, x, y, r);
  ctx.arcTo(x, y, x + width, y, r);
  ctx.closePath();
}

function drawRadar() {
  const canvas = $("radar");
  const { ctx, w, h } = resizeCanvas(canvas);
  ctx.clearRect(0, 0, w, h);

  const background = ctx.createLinearGradient(0, 0, w, h);
  background.addColorStop(0, "rgba(8, 27, 44, 0.54)");
  background.addColorStop(1, "rgba(4, 14, 24, 0.78)");
  ctx.fillStyle = background;
  ctx.fillRect(0, 0, w, h);

  ctx.strokeStyle = "rgba(116, 170, 205, 0.075)";
  ctx.lineWidth = 1;
  for (let x = 20; x < w; x += 42) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, h);
    ctx.stroke();
  }
  for (let y = 20; y < h; y += 42) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }

  if (!snapshot) {
    ctx.fillStyle = "#8da4b8";
    ctx.font = "12px 'Segoe UI', sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("Waiting for simulation…", w / 2, h / 2);
    return;
  }

  const t = displayTime();
  const approach = snapshot.final_approach;
  const faf = Math.max(1, approach.faf_distance_nm);
  const pathY = h * 0.66;
  const pathStart = Math.max(34, w * 0.08);
  const runwayX = w * 0.76;
  const runwayEnd = w * 0.95;
  const runwayTop = pathY - 22;
  const runwayBottom = pathY + 22;

  const xForDistance = (distance) => {
    const clamped = Math.max(0, Math.min(faf, distance));
    return runwayX - (clamped / faf) * (runwayX - pathStart);
  };

  // final approach corridor
  ctx.save();
  ctx.strokeStyle = "rgba(69, 214, 232, 0.26)";
  ctx.lineWidth = 22;
  ctx.beginPath();
  ctx.moveTo(pathStart, pathY);
  ctx.lineTo(runwayX, pathY);
  ctx.stroke();
  ctx.restore();

  ctx.strokeStyle = "rgba(69, 214, 232, 0.78)";
  ctx.lineWidth = 1.5;
  ctx.setLineDash([8, 8]);
  ctx.beginPath();
  ctx.moveTo(pathStart, pathY);
  ctx.lineTo(runwayX, pathY);
  ctx.stroke();
  ctx.setLineDash([]);

  ctx.fillStyle = "#6f8ba1";
  ctx.font = "10px 'Segoe UI', sans-serif";
  ctx.textAlign = "center";
  for (let distance = 0; distance <= faf; distance += 2) {
    const x = xForDistance(distance);
    ctx.strokeStyle = "rgba(141, 164, 184, 0.34)";
    ctx.beginPath();
    ctx.moveTo(x, pathY - 7);
    ctx.lineTo(x, pathY + 7);
    ctx.stroke();
    ctx.fillText(`${distance}`, x, pathY + 22);
  }
  ctx.fillStyle = "#6f8ba1";
  ctx.textAlign = "left";
  ctx.fillText("FAF", pathStart, pathY - 18);
  ctx.textAlign = "right";
  ctx.fillText("THRESHOLD", runwayX - 4, pathY - 18);

  // runway
  const occupied = snapshot.runway.status === "occupied";
  ctx.fillStyle = occupied ? "rgba(244, 162, 97, 0.22)" : "rgba(123, 211, 137, 0.11)";
  ctx.strokeStyle = occupied ? "#f4a261" : "rgba(123, 211, 137, 0.8)";
  ctx.lineWidth = 1.5;
  roundRect(ctx, runwayX, runwayTop, runwayEnd - runwayX, runwayBottom - runwayTop, 4);
  ctx.fill();
  ctx.stroke();

  ctx.strokeStyle = occupied ? "rgba(244, 162, 97, 0.9)" : "rgba(123, 211, 137, 0.55)";
  ctx.lineWidth = 1;
  ctx.setLineDash([10, 8]);
  ctx.beginPath();
  ctx.moveTo(runwayX + 8, pathY);
  ctx.lineTo(runwayEnd - 8, pathY);
  ctx.stroke();
  ctx.setLineDash([]);

  ctx.fillStyle = occupied ? "#ffd4ab" : "#bdecc6";
  ctx.font = "650 10px 'Segoe UI', sans-serif";
  ctx.textAlign = "center";
  ctx.fillText(`RWY ${snapshot.airport.runway}`, (runwayX + runwayEnd) / 2, pathY - 30);

  // recent landing pulses
  for (const flight of snapshot.flights) {
    const age = t - flight.actual;
    if (age >= 0 && age < 7) {
      const alpha = 1 - age / 7;
      ctx.beginPath();
      ctx.arc(runwayX + 14, pathY, 5 + age * 2.2, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(123, 211, 137, ${0.55 * alpha})`;
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }
  }

  // holding stack
  drawHoldingStack(ctx, t, w, h);

  // final aircraft
  for (const flight of snapshot.flights) {
    const status = statusAt(flight, t);
    if (status !== "final") continue;
    const position = positionAt(flight, t);
    if (position == null) continue;
    const x = xForDistance(position);
    const selected = flight.id === selectedId;

    ctx.beginPath();
    ctx.arc(x, pathY, selected ? 10 : 7, 0, Math.PI * 2);
    ctx.fillStyle = selected ? "rgba(69, 214, 232, 0.24)" : "rgba(46, 196, 182, 0.16)";
    ctx.fill();

    ctx.beginPath();
    ctx.arc(x, pathY, selected ? 5 : 3.6, 0, Math.PI * 2);
    ctx.fillStyle = "#2ec4b6";
    ctx.fill();

    if (selected) {
      ctx.beginPath();
      ctx.arc(x, pathY, 13, 0, Math.PI * 2);
      ctx.strokeStyle = "#45d6e8";
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }

    ctx.textAlign = "center";
    ctx.fillStyle = "#e0fff9";
    ctx.font = "650 10px 'Segoe UI', sans-serif";
    ctx.fillText(flight.callsign, x, pathY - 14);
    ctx.fillStyle = "rgba(141, 164, 184, 0.95)";
    ctx.font = "9px 'Cascadia Mono', Consolas, monospace";
    ctx.fillText(`${position.toFixed(1)} NM`, x, pathY + 34);
  }

  // runway occupant
  if (snapshot.runway.current_flight) {
    const occupant = snapshot.flights.find(
      (flight) => flight.callsign === snapshot.runway.current_flight
    );
    if (occupant) {
      ctx.beginPath();
      ctx.arc((runwayX + runwayEnd) / 2, pathY, 5, 0, Math.PI * 2);
      ctx.fillStyle = "#f4a261";
      ctx.fill();
      ctx.fillStyle = "#ffd9b5";
      ctx.font = "650 10px 'Segoe UI', sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(occupant.callsign, (runwayX + runwayEnd) / 2, pathY + 36);
    }
  }

  // HUD
  ctx.textAlign = "left";
  ctx.fillStyle = "#8da4b8";
  ctx.font = "10px 'Cascadia Mono', Consolas, monospace";
  ctx.fillText(`T+${fmtClock(t)}`, 18, 24);
  ctx.fillText(
    `${snapshot.metrics.final} on final · ${snapshot.metrics.holding} holding`,
    18,
    40
  );

  if (snapshot.paused) {
    ctx.fillStyle = "#f4a261";
    ctx.font = "700 11px 'Segoe UI', sans-serif";
    ctx.textAlign = "right";
    ctx.fillText("PAUSED", w - 18, 25);
  }
}

function drawHoldingStack(ctx, t, w, h) {
  const holding = snapshot.flights
    .filter((flight) => statusAt(flight, t) === "holding")
    .sort((a, b) => a.scheduled - b.scheduled);
  if (!holding.length) return;

  const x = 18;
  const y = 46;
  const width = Math.min(300, Math.max(190, w * 0.34));
  const rowHeight = 19;
  const maxRows = Math.max(2, Math.min(7, Math.floor((h * 0.66 - y - 55) / rowHeight)));
  const visible = holding.slice(0, maxRows);
  const height = 34 + visible.length * rowHeight + (holding.length > visible.length ? 18 : 0);

  ctx.fillStyle = "rgba(10, 26, 41, 0.78)";
  ctx.strokeStyle = "rgba(244, 162, 97, 0.28)";
  ctx.lineWidth = 1;
  roundRect(ctx, x, y, width, height, 9);
  ctx.fill();
  ctx.stroke();

  ctx.textAlign = "left";
  ctx.fillStyle = "#f4a261";
  ctx.font = "700 9px 'Segoe UI', sans-serif";
  ctx.fillText(`HOLDING STACK · ${holding.length}`, x + 11, y + 16);

  visible.forEach((flight, index) => {
    const rowY = y + 32 + index * rowHeight;
    if (flight.id === selectedId) {
      ctx.fillStyle = "rgba(69, 214, 232, 0.14)";
      roundRect(ctx, x + 6, rowY - 11, width - 12, 16, 4);
      ctx.fill();
    }
    ctx.beginPath();
    ctx.arc(x + 13, rowY - 3, 2.4, 0, Math.PI * 2);
    ctx.fillStyle = "#f4a261";
    ctx.fill();

    ctx.fillStyle = flight.id === selectedId ? "#9ceef7" : "#d9e8f2";
    ctx.font = "600 9.5px 'Segoe UI', sans-serif";
    ctx.textAlign = "left";
    ctx.fillText(flight.callsign, x + 22, rowY);

    ctx.fillStyle = "#8da4b8";
    ctx.font = "9px 'Cascadia Mono', Consolas, monospace";
    ctx.textAlign = "right";
    ctx.fillText(`+${fmtDelay(flight.delay)}`, x + width - 11, rowY);
  });

  if (holding.length > visible.length) {
    ctx.fillStyle = "#6f8ba1";
    ctx.font = "9px 'Segoe UI', sans-serif";
    ctx.textAlign = "left";
    ctx.fillText(`+${holding.length - visible.length} more holding`, x + 13, y + height - 8);
  }
}

/* ------------------------------- timeline -------------------------------- */

function drawTimeline() {
  const canvas = $("timeline");
  const { ctx, w, h } = resizeCanvas(canvas);
  ctx.clearRect(0, 0, w, h);

  if (!snapshot) {
    ctx.fillStyle = "#8da4b8";
    ctx.font = "12px 'Segoe UI', sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("Waiting for simulation…", w / 2, h / 2);
    return;
  }

  const now = snapshot.sim_time;
  const flights = [...snapshot.flights].sort((a, b) => a.assigned - b.assigned);
  let rows = flights.filter((flight) => flight.assigned >= now - 240).slice(0, 18);
  if (rows.length < 8) {
    const earlier = flights.filter((flight) => flight.assigned < now - 240).slice(-8);
    rows = [...earlier, ...rows].slice(-18);
  }
  if (!rows.length) rows = flights.slice(0, 18);

  const labelWidth = Math.min(92, Math.max(66, w * 0.12));
  const top = 30;
  const bottom = 14;
  const rowHeight = Math.max(6, Math.min(16, (h - top - bottom) / Math.max(rows.length, 1)));
  const left = labelWidth;
  const right = w - 14;

  let start = Math.min(now - 150, ...rows.map((flight) => flight.scheduled));
  let end = Math.max(
    now + 300,
    ...rows.map((flight) => flight.assigned + snapshot.runway.occupancy_sec + 60),
    ...rows.map((flight) => flight.actual)
  );
  if (!Number.isFinite(start)) start = now - 180;
  if (!Number.isFinite(end)) end = now + 900;
  const padding = Math.max(30, (end - start) * 0.04);
  start = Math.max(snapshot.scenario.start_time, start - padding);
  end += padding;

  const xFor = (time) => left + ((time - start) / Math.max(1, end - start)) * (right - left);

  // time grid
  const intervals = [60, 120, 300, 600, 900, 1800, 3600];
  const target = (end - start) / 6;
  const step = intervals.find((value) => value >= target) || 3600;
  const firstTick = Math.ceil(start / step) * step;

  ctx.textAlign = "center";
  ctx.font = "9px 'Cascadia Mono', Consolas, monospace";
  for (let time = firstTick; time <= end; time += step) {
    const x = xFor(time);
    ctx.strokeStyle = "rgba(116, 170, 205, 0.10)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x, top - 10);
    ctx.lineTo(x, h - bottom);
    ctx.stroke();
    ctx.fillStyle = "#607a90";
    ctx.fillText(fmtClock(time).slice(0, 5), x, 15);
  }

  // rows
  rows.forEach((flight, index) => {
    const y = top + index * rowHeight + rowHeight / 2;
    const isSelected = flight.id === selectedId;
    const meta = statusInfo(flight.status);

    if (index % 2 === 0) {
      ctx.fillStyle = "rgba(116, 170, 205, 0.035)";
      ctx.fillRect(left, y - rowHeight / 2, right - left, rowHeight);
    }

    ctx.textAlign = "left";
    ctx.font = "9.5px 'Segoe UI', sans-serif";
    ctx.fillStyle = isSelected ? "#8beeff" : "#8da4b8";
    ctx.fillText(flight.callsign, 8, y + 3);

    // scheduled marker
    if (flight.scheduled >= start && flight.scheduled <= end) {
      const sx = xFor(flight.scheduled);
      ctx.beginPath();
      ctx.arc(sx, y, 2.6, 0, Math.PI * 2);
      ctx.strokeStyle = "#7c93a8";
      ctx.lineWidth = 1;
      ctx.stroke();
    }

    // assigned runway slot
    const slotStart = Math.max(start, flight.assigned);
    const slotEnd = Math.min(end, flight.assigned + snapshot.runway.occupancy_sec);
    if (slotEnd > slotStart) {
      const barX = xFor(slotStart);
      const barWidth = Math.max(3, xFor(slotEnd) - barX);
      ctx.fillStyle = meta.color;
      ctx.globalAlpha = flight.status === "scheduled" ? 0.34 : 0.78;
      roundRect(ctx, barX, y - Math.max(1.5, rowHeight * 0.20), barWidth, Math.max(3, rowHeight * 0.40), 2);
      ctx.fill();
      ctx.globalAlpha = 1;
    }

    // actual landing marker
    if (flight.status === "landed" && flight.actual >= start && flight.actual <= end) {
      const ax = xFor(flight.actual);
      ctx.beginPath();
      ctx.arc(ax, y, 2.4, 0, Math.PI * 2);
      ctx.fillStyle = "#7bd389";
      ctx.fill();
    }

    if (isSelected) {
      ctx.strokeStyle = "rgba(69, 214, 232, 0.55)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(left, y - rowHeight / 2);
      ctx.lineTo(right, y - rowHeight / 2);
      ctx.stroke();
    }
  });

  // now marker
  const nowX = xFor(now);
  ctx.strokeStyle = "rgba(69, 214, 232, 0.9)";
  ctx.lineWidth = 1.5;
  ctx.setLineDash([4, 4]);
  ctx.beginPath();
  ctx.moveTo(nowX, top - 10);
  ctx.lineTo(nowX, h - bottom);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = "#45d6e8";
  ctx.font = "700 8.5px 'Segoe UI', sans-serif";
  ctx.textAlign = "center";
  ctx.fillText("NOW", nowX, h - 4);
}

/* -------------------------------- network -------------------------------- */

function connect() {
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
    return;
  }
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${protocol}://${location.host}/ws`);
  socket = ws;

  ws.addEventListener("open", () => setConnection("live", "ok"));
  ws.addEventListener("message", (event) => {
    try {
      applySnapshot(JSON.parse(event.data));
    } catch (error) {
      console.error("Invalid snapshot", error);
    }
  });
  ws.addEventListener("close", () => {
    setConnection("reconnecting", "warn");
    if (socket === ws) socket = null;
    clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(connect, 1200);
  });
  ws.addEventListener("error", () => {
    try {
      ws.close();
    } catch (error) {
      /* ignore */
    }
  });
}

async function fetchState() {
  try {
    const response = await fetch("/api/state", { cache: "no-store" });
    if (!response.ok) throw new Error(`State request failed (${response.status})`);
    applySnapshot(await response.json());
  } catch (error) {
    setConnection("offline", "warn");
  }
}

async function postControl(payload, options = {}) {
  try {
    const response = await fetch("/api/control", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      throw new Error(detail.detail || `Control failed (${response.status})`);
    }
    if (options.clearSelection) selectedId = null;
    applySnapshot(await response.json());
    if (options.message) showToast(options.message);
  } catch (error) {
    showToast(error.message || "Control request failed", true);
  }
}

async function postScenario(payload) {
  try {
    const response = await fetch("/api/scenario", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      throw new Error(detail.detail || `Scenario failed (${response.status})`);
    }
    selectedId = null;
    formInitialized = false;
    applySnapshot(await response.json());
    showToast(`Generated ${payload.flights} flights with seed ${payload.seed}.`);
  } catch (error) {
    showToast(error.message || "Scenario request failed", true);
  }
}

function showToast(message, isError = false) {
  const element = $("toast");
  element.textContent = message;
  element.className = `toast show${isError ? " error" : ""}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    element.className = "toast";
  }, 2800);
}

/* -------------------------------- events --------------------------------- */

function bindEvents() {
  $("pauseBtn").addEventListener("click", () => postControl({ action: "toggle" }));
  $("resetBtn").addEventListener("click", () =>
    postControl({ action: "reset" }, { clearSelection: true, message: "Scenario reset." })
  );

  $("speedSelect").addEventListener("change", (event) => {
    postControl({ action: "speed", value: Number(event.target.value) });
  });

  $("scenarioForm").addEventListener("submit", (event) => {
    event.preventDefault();
    const flights = Number($("flightsInput").value);
    const seed = Number($("seedInput").value);
    const rate = Number($("rateInput").value);
    const strategy = $("strategySelect").value;
    if (!Number.isFinite(flights) || flights < 1 || flights > 1000) {
      showToast("Flights must be between 1 and 1000.", true);
      return;
    }
    if (!Number.isFinite(seed)) {
      showToast("Seed must be a number.", true);
      return;
    }
    if (!Number.isFinite(rate) || rate <= 0) {
      showToast("Arrival rate must be positive.", true);
      return;
    }
    postScenario({ flights, seed, strategy, rate });
  });

  $("searchInput").addEventListener("input", (event) => {
    searchText = event.target.value;
    renderBoard();
  });
  $("filterSelect").addEventListener("change", (event) => {
    filterStatus = event.target.value;
    renderBoard();
  });

  $("flightBody").addEventListener("click", (event) => {
    const row = event.target.closest("tr[data-id]");
    if (!row) return;
    selectedId = row.dataset.id;
    renderBoard();
    renderDetail();
    drawRadar();
  });

  document.querySelectorAll("th[data-sort]").forEach((header) => {
    header.addEventListener("click", () => {
      const key = header.dataset.sort;
      if (sortKey === key) {
        sortDir *= -1;
      } else {
        sortKey = key;
        sortDir = 1;
      }
      renderBoard();
    });
  });

  $("closeDetail").addEventListener("click", () => {
    selectedId = null;
    renderBoard();
    renderDetail();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      selectedId = null;
      renderBoard();
      renderDetail();
      return;
    }
    if (
      event.code === "Space" &&
      !["INPUT", "SELECT", "TEXTAREA", "BUTTON"].includes(event.target.tagName)
    ) {
      event.preventDefault();
      postControl({ action: "toggle" });
    }
  });

  window.addEventListener("resize", () => {
    drawRadar();
    drawTimeline();
  });
}

/* --------------------------------- boot ---------------------------------- */

function animate() {
  if (snapshot) {
    $("clock").textContent = fmtClock(displayTime());
    drawRadar();
  }
  requestAnimationFrame(animate);
}

function boot() {
  bindEvents();
  fetchState().finally(connect);
  setInterval(() => {
    if (!snapshot || performance.now() - receivedAt > 3000) {
      fetchState();
    }
  }, 3000);
  animate();
}

boot();
