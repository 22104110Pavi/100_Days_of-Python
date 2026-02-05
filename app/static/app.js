const hazardLabel = document.getElementById("hazard-label");
const hazardScore = document.getElementById("hazard-score");
const anomalyLabel = document.getElementById("anomaly-label");
const anomalyScore = document.getElementById("anomaly-score");
const ingestStatus = document.getElementById("ingest-status");
const lastUpdate = document.getElementById("last-update");
const alertGrid = document.getElementById("alert-grid");
const logBody = document.getElementById("log-body");
const workerRecommendation = document.getElementById("worker-recommendation");
const workerStress = document.getElementById("worker-stress");

const sectionTargets = {
  dashboard: document.getElementById("dashboard"),
  industrial: document.getElementById("industrial"),
  workers: document.getElementById("workers"),
  alerts: document.getElementById("alerts"),
  log: document.getElementById("log"),
};

const navButtons = document.querySelectorAll(".nav-item");
navButtons.forEach((button) => {
  button.addEventListener("click", () => {
    navButtons.forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    const target = button.dataset.target;
    Object.entries(sectionTargets).forEach(([key, section]) => {
      if (section) {
        section.classList.toggle("hidden", key !== target);
      }
    });
  });
});

const charts = {};
const chartConfig = {
  hazard: { id: "chart-hazard", label: "Hazard Score", color: "#ff9db0" },
  temp: { id: "chart-temp", label: "Temperature (°C)", color: "#6DA8FF" },
  humidity: { id: "chart-humidity", label: "Humidity (%)", color: "#63D6B4" },
  mq135: { id: "chart-mq135", label: "MQ135 (ppm)", color: "#F6C15B" },
  dust: { id: "chart-dust", label: "Dust (µg/m³)", color: "#FF8D8D" },
  sound: { id: "chart-sound", label: "Sound (dB)", color: "#9F7BFF" },
  heart: { id: "chart-heart", label: "Heart Rate (bpm)", color: "#FF6FA1" },
  spo2: { id: "chart-spo2", label: "SpO₂ (%)", color: "#6ce5ff" },
  motion: { id: "chart-motion", label: "Fall Detection (g)", color: "#51B2FF" },
  bodyTemp: { id: "chart-body-temp", label: "Body Temp (°C)", color: "#FFB36A" },
};

function buildLineChart(canvasId, label, color) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;
  return new Chart(ctx, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label,
          data: [],
          borderColor: color,
          backgroundColor: `${color}33`,
          fill: true,
          tension: 0.32,
          borderWidth: 2,
          pointRadius: 0,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: false,
        },
      },
      scales: {
        x: {
          ticks: { color: "rgba(255,255,255,0.5)" },
          grid: { color: "rgba(255,255,255,0.05)" },
        },
        y: {
          ticks: { color: "rgba(255,255,255,0.5)" },
          grid: { color: "rgba(255,255,255,0.05)" },
        },
      },
    },
  });
}

Object.values(chartConfig).forEach((config) => {
  charts[config.id] = buildLineChart(config.id, config.label, config.color);
});

function updateCharts(history) {
  if (!history.length) return;
  const labels = history.map((row) => row.timestamp ?? "");

  const mapValues = (key) =>
    history.map((row) => {
      const value = row[key];
      return typeof value === "number" && !Number.isNaN(value) ? value : null;
    });

  const dataMap = {
    "chart-temp": mapValues("temperature_c"),
    "chart-humidity": mapValues("humidity_percent"),
    "chart-mq135": mapValues("mq135_ppm"),
    "chart-dust": mapValues("dust_ug_m3"),
    "chart-sound": mapValues("sound_db"),
    "chart-heart": mapValues("heart_rate_bpm"),
    "chart-spo2": mapValues("spo2_percent"),
    "chart-motion": mapValues("motion_g"),
    "chart-body-temp": mapValues("body_temp_c"),
  };

  Object.entries(dataMap).forEach(([chartId, values]) => {
    const chart = charts[chartId];
    if (chart) {
      chart.data.labels = labels;
      chart.data.datasets[0].data = values;
      chart.update();
    }
  });
}

function updateHazardTrend(trend) {
  if (!trend.length) return;
  const chart = charts["chart-hazard"];
  if (!chart) return;
  chart.data.labels = trend.map((row) => row.timestamp);
  chart.data.datasets[0].data = trend.map((row) => row.hazard_score);
  chart.update();
}

function setStatusLabel(evaluation) {
  const riskLabel = evaluation.risk_label ?? "Unknown";
  hazardLabel.textContent = riskLabel;
  hazardScore.textContent =
    evaluation.hazard_score !== null && evaluation.hazard_score !== undefined
      ? `Hazard score: ${(evaluation.hazard_score * 100).toFixed(1)}%`
      : "Hazard score: --";

  anomalyLabel.textContent = evaluation.anomaly_score === null ? "Pending" : "Monitored";
  anomalyScore.textContent =
    evaluation.anomaly_score !== null && evaluation.anomaly_score !== undefined
      ? `Anomaly score: ${evaluation.anomaly_score.toFixed(3)}`
      : "Anomaly score: --";
}

function renderAlerts(evaluation, latestEnv, latestWorker) {
  const alerts = [];
  if (evaluation.risk_label === "Critical") {
    alerts.push({
      title: "Critical hazard classification",
      description: "Random Forest flagged severe conditions.",
    });
  } else if (evaluation.risk_label === "Warning") {
    alerts.push({
      title: "Warning hazard classification",
      description: "Random Forest flagged elevated risk.",
    });
  }

  if (evaluation.anomaly_score !== null && evaluation.anomaly_score < -0.2) {
    alerts.push({
      title: "Isolation Forest anomaly",
      description: "Anomaly score indicates unusual sensor behavior.",
    });
  }

  if (!latestEnv && !latestWorker) {
    alerts.push({
      title: "No live feeds",
      description: "Configure ThingSpeak keys to ingest live data.",
    });
  }

  if (!alerts.length) {
    alerts.push({
      title: "All systems nominal",
      description: "No active alerts detected.",
    });
  }

  alertGrid.innerHTML = "";
  alerts.forEach((alert) => {
    const card = document.createElement("div");
    card.className = "alert-card";
    card.innerHTML = `
      <div>
        <h4>${alert.title}</h4>
        <span>${alert.description}</span>
      </div>
      <div class="alert-card__status">Live</div>
    `;
    alertGrid.appendChild(card);
  });
}

function renderLog(history) {
  logBody.innerHTML = "";
  const rows = history.slice(-20).reverse();
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${row.timestamp ?? "—"}</td>
      <td>${formatValue(row.temperature_c)}</td>
      <td>${formatValue(row.humidity_percent)}</td>
      <td>${formatValue(row.mq135_ppm)}</td>
      <td>${formatValue(row.dust_ug_m3)}</td>
      <td>${formatValue(row.sound_db)}</td>
      <td>${formatValue(row.heart_rate_bpm)}</td>
      <td>${formatValue(row.spo2_percent)}</td>
      <td>${formatValue(row.motion_g)}</td>
      <td>${formatValue(row.body_temp_c)}</td>
    `;
    logBody.appendChild(tr);
  });
}

function updateWorkerInsights(latestWorker) {
  if (!latestWorker) {
    workerRecommendation.textContent = "Pending data ingestion.";
    workerStress.textContent = "Awaiting MAX30102 inputs.";
    return;
  }

  const heartRate = latestWorker.heart_rate_bpm;
  if (typeof heartRate === "number" && heartRate > 110) {
    workerRecommendation.textContent =
      "High stress detected. Recommend a 3-5 minute micro break.";
    workerStress.textContent = "Elevated heart rate (MAX30102).";
  } else if (typeof heartRate === "number" && heartRate > 90) {
    workerRecommendation.textContent =
      "Moderate workload detected. Consider a short hydration break.";
    workerStress.textContent = "Moderate heart rate variability.";
  } else if (typeof heartRate === "number") {
    workerRecommendation.textContent =
      "Worker vitals stable. Continue monitoring for fatigue.";
    workerStress.textContent = "Normal range heart rate.";
  } else {
    workerRecommendation.textContent = "Pending data ingestion.";
    workerStress.textContent = "Awaiting MAX30102 inputs.";
  }
}

function formatValue(value) {
  return typeof value === "number" && !Number.isNaN(value) ? value.toFixed(2) : "—";
}

function setIngestState(isOnline, timestamp) {
  ingestStatus.textContent = isOnline ? "Online" : "Offline";
  ingestStatus.style.background = isOnline
    ? "rgba(65, 209, 166, 0.2)"
    : "rgba(255, 92, 122, 0.15)";
  ingestStatus.style.color = isOnline ? "#8ff0d1" : "#ff9db0";
  lastUpdate.textContent = timestamp || "—";
}

async function pollStatus() {
  try {
    const response = await fetch("/api/status");
    if (!response.ok) throw new Error("Status fetch failed");
    const payload = await response.json();
    setStatusLabel(payload.evaluation ?? {});
    const latestEnv = payload.env_latest?.[0];
    const latestWorker = payload.worker_latest?.[0];
    const timestamp = latestEnv?.timestamp || latestWorker?.timestamp;
    setIngestState(true, timestamp);
    renderAlerts(payload.evaluation ?? {}, latestEnv, latestWorker);
    updateWorkerInsights(latestWorker);
  } catch (error) {
    setIngestState(false, "—");
  }
}

async function pollHistory() {
  try {
    const response = await fetch("/api/history?results=120");
    if (!response.ok) throw new Error("History fetch failed");
    const payload = await response.json();
    const combined = payload.combined_history ?? [];
    updateCharts(combined);
    renderLog(combined);
  } catch (error) {
    renderLog([]);
  }
}

async function pollHazardTrend() {
  try {
    const response = await fetch("/api/hazard-trend?results=120");
    if (!response.ok) throw new Error("Hazard trend fetch failed");
    const payload = await response.json();
    updateHazardTrend(payload.hazard_trend ?? []);
  } catch (error) {
    // keep last chart state
  }
}

pollStatus();
pollHistory();
pollHazardTrend();
setInterval(() => {
  pollStatus();
  pollHistory();
  pollHazardTrend();
}, 15000);
