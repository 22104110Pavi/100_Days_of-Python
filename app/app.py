import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests
from flask import Flask, jsonify, render_template, request
from sklearn.ensemble import IsolationForest, RandomForestClassifier

app = Flask(__name__)


@dataclass
class ThingSpeakChannel:
    name: str
    channel_id: str
    read_api_key: str
    field_map: Dict[str, str]


ENV_CHANNEL = ThingSpeakChannel(
    name="environment",
    channel_id=os.environ.get("TS_ENV_CHANNEL_ID", ""),
    read_api_key=os.environ.get("TS_ENV_READ_KEY", ""),
    field_map={
        "temperature_c": "field1",
        "humidity_percent": "field2",
        "mq135_ppm": "field3",
        "dust_ug_m3": "field4",
        "sound_db": "field5",
    },
)

WORKER_CHANNEL = ThingSpeakChannel(
    name="worker",
    channel_id=os.environ.get("TS_WORKER_CHANNEL_ID", ""),
    read_api_key=os.environ.get("TS_WORKER_READ_KEY", ""),
    field_map={
        "heart_rate_bpm": "field1",
        "spo2_percent": "field2",
        "motion_g": "field3",
        "body_temp_c": "field4",
    },
)


def _read_env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    try:
        return float(raw) if raw is not None else default
    except ValueError:
        return default


def fetch_thingspeak_channel(
    channel: ThingSpeakChannel, results: int = 120
) -> List[Dict[str, Any]]:
    if not channel.channel_id or not channel.read_api_key:
        return []
    url = (
        f"https://api.thingspeak.com/channels/{channel.channel_id}/feeds.json"
        f"?api_key={channel.read_api_key}&results={results}"
    )
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    payload = response.json()
    return payload.get("feeds", [])


def _parse_feeds(
    feeds: List[Dict[str, Any]], field_map: Dict[str, str]
) -> pd.DataFrame:
    if not feeds:
        return pd.DataFrame()
    rows: List[Dict[str, Any]] = []
    for feed in feeds:
        row: Dict[str, Any] = {}
        for name, field in field_map.items():
            value = feed.get(field)
            try:
                row[name] = float(value) if value is not None else np.nan
            except (TypeError, ValueError):
                row[name] = np.nan
        timestamp = feed.get("created_at")
        if timestamp:
            row["timestamp"] = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        rows.append(row)
    frame = pd.DataFrame(rows).dropna(how="all")
    if not frame.empty:
        frame = frame.sort_values("timestamp")
    return frame


def _serialize_frame(frame: pd.DataFrame) -> List[Dict[str, Any]]:
    if frame.empty:
        return []
    result = frame.copy()
    if "timestamp" in result.columns:
        result["timestamp"] = result["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    return result.to_dict(orient="records")


def build_feature_frame(
    env_frame: pd.DataFrame, worker_frame: pd.DataFrame
) -> pd.DataFrame:
    if env_frame.empty and worker_frame.empty:
        return pd.DataFrame()

    env_frame = env_frame.copy()
    worker_frame = worker_frame.copy()

    for frame in (env_frame, worker_frame):
        if not frame.empty:
            frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)

    if not env_frame.empty and not worker_frame.empty:
        merged = pd.merge_asof(
            env_frame.sort_values("timestamp"),
            worker_frame.sort_values("timestamp"),
            on="timestamp",
            direction="nearest",
            tolerance=pd.Timedelta("5min"),
        )
    elif not env_frame.empty:
        merged = env_frame
    else:
        merged = worker_frame

    merged = merged.dropna(how="all").reset_index(drop=True)
    return merged


def generate_labels(frame: pd.DataFrame) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype=int)

    temp = frame.get("temperature_c", pd.Series(dtype=float))
    humidity = frame.get("humidity_percent", pd.Series(dtype=float))
    mq135 = frame.get("mq135_ppm", pd.Series(dtype=float))
    dust = frame.get("dust_ug_m3", pd.Series(dtype=float))
    sound = frame.get("sound_db", pd.Series(dtype=float))
    heart = frame.get("heart_rate_bpm", pd.Series(dtype=float))
    motion = frame.get("motion_g", pd.Series(dtype=float))
    body_temp = frame.get("body_temp_c", pd.Series(dtype=float))

    risk = (
        (temp > _read_env_float("TH_TEMP_HIGH", 40.0))
        | (humidity > _read_env_float("TH_HUMIDITY_HIGH", 85.0))
        | (mq135 > _read_env_float("TH_MQ135_HIGH", 300.0))
        | (dust > _read_env_float("TH_DUST_HIGH", 150.0))
        | (sound > _read_env_float("TH_SOUND_HIGH", 90.0))
        | (heart > _read_env_float("TH_HEART_HIGH", 120.0))
        | (motion > _read_env_float("TH_MOTION_HIGH", 3.0))
        | (body_temp > _read_env_float("TH_BODY_TEMP_HIGH", 38.0))
    )

    return risk.fillna(False).astype(int)


def train_models(frame: pd.DataFrame) -> Tuple[Optional[RandomForestClassifier], Optional[IsolationForest]]:
    if frame.empty or len(frame) < 10:
        return None, None

    features = frame.drop(columns=["timestamp"], errors="ignore")
    features = features.fillna(features.median(numeric_only=True))

    labels = generate_labels(frame)
    if labels.nunique() < 2:
        labels = (features.sum(axis=1) > features.sum(axis=1).median()).astype(int)

    rf = RandomForestClassifier(
        n_estimators=200, max_depth=6, random_state=42, class_weight="balanced"
    )
    rf.fit(features, labels)

    iso = IsolationForest(
        n_estimators=200, contamination=0.12, random_state=42
    )
    iso.fit(features)

    return rf, iso


def evaluate_latest(
    frame: pd.DataFrame,
) -> Dict[str, Any]:
    if frame.empty:
        return {
            "status": "no-data",
            "risk_label": "Unknown",
            "hazard_score": None,
            "anomaly_score": None,
            "latest": {},
        }

    rf_model, iso_model = train_models(frame)
    latest = frame.tail(1).drop(columns=["timestamp"], errors="ignore")
    latest = latest.fillna(latest.median(numeric_only=True))

    hazard_score = None
    hazard_label = "Unknown"
    if rf_model is not None:
        hazard_score = float(rf_model.predict_proba(latest)[0][1])
        if hazard_score >= 0.75:
            hazard_label = "Critical"
        elif hazard_score >= 0.5:
            hazard_label = "Warning"
        else:
            hazard_label = "Normal"

    anomaly_score = None
    if iso_model is not None:
        anomaly_score = float(iso_model.decision_function(latest)[0])

    return {
        "status": "ok",
        "risk_label": hazard_label,
        "hazard_score": hazard_score,
        "anomaly_score": anomaly_score,
        "latest": latest.to_dict(orient="records")[0],
    }


def compute_hazard_trend(frame: pd.DataFrame) -> List[Dict[str, Any]]:
    if frame.empty or len(frame) < 10:
        return []

    features = frame.drop(columns=["timestamp"], errors="ignore")
    features = features.fillna(features.median(numeric_only=True))

    labels = generate_labels(frame)
    if labels.nunique() < 2:
        labels = (features.sum(axis=1) > features.sum(axis=1).median()).astype(int)

    rf = RandomForestClassifier(
        n_estimators=200, max_depth=6, random_state=42, class_weight="balanced"
    )
    rf.fit(features, labels)
    scores = rf.predict_proba(features)[:, 1]

    trend = []
    for timestamp, score in zip(frame["timestamp"], scores):
        trend.append(
            {
                "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "hazard_score": float(score),
            }
        )
    return trend


@app.route("/")
def index() -> str:
    return render_template("index.html")


@app.route("/api/status")
def api_status() -> Any:
    env_feeds = fetch_thingspeak_channel(ENV_CHANNEL)
    worker_feeds = fetch_thingspeak_channel(WORKER_CHANNEL)

    env_frame = _parse_feeds(env_feeds, ENV_CHANNEL.field_map)
    worker_frame = _parse_feeds(worker_feeds, WORKER_CHANNEL.field_map)
    combined = build_feature_frame(env_frame, worker_frame)

    evaluation = evaluate_latest(combined)
    response = {
        "evaluation": evaluation,
        "env_latest": _serialize_frame(env_frame.tail(1)),
        "worker_latest": _serialize_frame(worker_frame.tail(1)),
    }
    return jsonify(response)


@app.route("/api/history")
def api_history() -> Any:
    results = request.args.get("results", default="120")
    try:
        results_count = max(10, min(int(results), 500))
    except ValueError:
        results_count = 120

    env_feeds = fetch_thingspeak_channel(ENV_CHANNEL, results=results_count)
    worker_feeds = fetch_thingspeak_channel(WORKER_CHANNEL, results=results_count)

    env_frame = _parse_feeds(env_feeds, ENV_CHANNEL.field_map)
    worker_frame = _parse_feeds(worker_feeds, WORKER_CHANNEL.field_map)
    combined = build_feature_frame(env_frame, worker_frame)

    response = {
        "env_history": _serialize_frame(env_frame),
        "worker_history": _serialize_frame(worker_frame),
        "combined_history": _serialize_frame(combined),
    }
    return jsonify(response)


@app.route("/api/hazard-trend")
def api_hazard_trend() -> Any:
    results = request.args.get("results", default="120")
    try:
        results_count = max(10, min(int(results), 500))
    except ValueError:
        results_count = 120

    env_feeds = fetch_thingspeak_channel(ENV_CHANNEL, results=results_count)
    worker_feeds = fetch_thingspeak_channel(WORKER_CHANNEL, results=results_count)

    env_frame = _parse_feeds(env_feeds, ENV_CHANNEL.field_map)
    worker_frame = _parse_feeds(worker_feeds, WORKER_CHANNEL.field_map)
    combined = build_feature_frame(env_frame, worker_frame)

    trend = compute_hazard_trend(combined)
    return jsonify({"hazard_trend": trend})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), debug=True)
