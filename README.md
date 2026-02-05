# Industrial Safety & Hazard Monitoring Dashboard

This app provides a professional industrial monitoring interface that consumes
ThingSpeak sensor feeds for environmental and worker safety parameters. It
runs Random Forest classification to estimate hazard risk and Isolation Forest
anomaly detection to surface abnormal patterns.

## Features

- Real-time ThingSpeak ingestion for environmental sensors: temperature,
  humidity, MQ135 air quality, GP2Y1010AUF dust, and LM393 sound.
- Worker monitoring inputs: MAX30102 heart rate, MPU6050 motion, and DSB body
  temperature.
- Random Forest hazard scoring with configurable thresholds.
- Isolation Forest anomaly scoring for early warnings.
- Responsive, executive-ready UI.

## Configure ThingSpeak

Set environment variables with your ThingSpeak channel IDs and read keys:

```bash
export TS_ENV_CHANNEL_ID="your_env_channel_id"
export TS_ENV_READ_KEY="your_env_read_key"
export TS_WORKER_CHANNEL_ID="your_worker_channel_id"
export TS_WORKER_READ_KEY="your_worker_read_key"
```

Optional safety thresholds can be tuned with:

- `TH_TEMP_HIGH`, `TH_HUMIDITY_HIGH`, `TH_MQ135_HIGH`, `TH_DUST_HIGH`,
  `TH_SOUND_HIGH`, `TH_HEART_HIGH`, `TH_MOTION_HIGH`, `TH_BODY_TEMP_HIGH`

## Run locally

```bash
python app/app.py
```

Open `http://localhost:8000` in your browser.

## Dependencies

The backend uses:

- Flask
- pandas
- numpy
- scikit-learn
- requests

Install with:

```bash
pip install flask pandas numpy scikit-learn requests
```
