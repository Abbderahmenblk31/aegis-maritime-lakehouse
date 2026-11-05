# 🚢 AegisSea: Maritime Telemetry & Port Congestion Lakehouse

[![Geospatial CI](https://github.com/your-username/aegis-maritime-lakehouse/actions/workflows/ci.yml/badge.svg)](https://github.com/your-username/aegis-maritime-lakehouse/actions)
[![DuckDB Spatial](https://img.shields.io/badge/Engine-DuckDB%20Spatial-yellow.svg)](https://duckdb.org/)
[![Data Source](https://img.shields.io/badge/Data-100%25%20Real%20AIS%20Telemetry-blue.svg)](https://www.digitraffic.fi/)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-brightgreen.svg)](https://python.org)

An enterprise-grade **Geospatial Data Engineering & Economic Analytics Platform** that ingests **100% genuine live AIS (Automatic Identification System) vessel telemetry** across Northern European shipping corridors, models spatial trajectories in an embedded **DuckDB Lakehouse**, and generates real-time **Port Congestion & Supply Chain Bottleneck Scorecards**.

---

## 📌 Executive Summary & Business Problem

Global supply chain disruptions and port congestion cost the global maritime economy over **$30 Billion annually** in vessel demurrage penalties, delayed goods, and idle fuel waste.

Unlike typical portfolio projects relying on synthetic or static CSVs, **AegisSea** connects directly to live national maritime broadcast transponders across the Baltic and Scandinavian waters. It continuously:
1. Ingests live satellite and coastal VHF radio broadcasts (MMSI, GPS coordinates, SOG, COG, Draught, Vessel Dimensions, and Destinations).
2. Cleans raw telemetry anomalies (such as ITU-R 102.3-knot sensor faults and GPS dropouts).
3. Executes spatial joins (Point-in-Radius geofencing) to monitor real-time vessel queues at major European strategic ports (Helsinki, Tallinn, Kotka-Hamina, Primorsk Oil Terminal, St. Petersburg, and Stockholm).
4. Produces actionable decision metrics: **Port Congestion Occupancy %**, **Tanker/Cargo Anchorage Queues**, and **Fleet Speed Drops**.

---

## 🏛️ System Architecture

```text
       [Live Open Maritime Transponder Stream]
      (Real-time AIS pings via National VHF Coastal Stations)
                                │
                                ▼
  ┌─────────────────────────────────────────────────────────────┐
  │                 INGESTION & BRONZE LAYER                    │
  │  • fetch_live_telemetry() & fetch_live_vessels_metadata()   │
  │  • Raw schema: MMSI, Lat/Lon, Speed, Draught, Destination   │
  │  • Geometric Point Synthesis: ST_Point(lon, lat)            │
  └─────────────────────────────┬───────────────────────────────┘
                                │
                                ▼
  ┌─────────────────────────────────────────────────────────────┐
  │             SILVER LAYER (CLEANSING & QUALITY)              │
  │  • ITU-R M.1371 Sensor Error Sanitization (102.3 kts -> NULL)│
  │  • Spatial Bounding Box Filter (Baltic / North Sea)         │
  │  • Navigational Status Mapping (Under Way, At Anchor, Moored│
  └─────────────────────────────┬───────────────────────────────┘
                                │
                                ▼
  ┌─────────────────────────────────────────────────────────────┐
  │             GOLD MARTS (SPATIAL DIMENSIONAL SQL)            │
  │  • dim_ports: Strategic port coordinates & anchorage radii   │
  │  • fct_vessel_port_proximity: Haversine / Spatial distance   │
  │  • mart_port_congestion: Bottleneck Scorecard & Waiting Rate│
  └─────────────────────────────┬───────────────────────────────┘
                                │
             ┌──────────────────┴──────────────────┐
             ▼                                     ▼
┌──────────────────────────────┐     ┌──────────────────────────────┐
│  AUTOMATED PYTEST CONTRACTS  │     │ 3D GEOSPATIAL BI DASHBOARD   │
│  • Speed error sanitization  │     │ • Streamlit + PyDeck GL      │
│  • Coordinate validity checks│     │ • Real-time 3D Vessel Map    │
│  • Zero-division mart tests  │     │ • Interactive Fleet Filter   │
└──────────────────────────────┘     └──────────────────────────────┘
```

---

## 📊 Live Production Output (Sample)

When running the spatial model against live data, the lakehouse outputs real-time supply chain bottlenecks:

```text
======================================================================
PORT CONGESTION & SUPPLY CHAIN BOTTLENECK SCORECARD (LIVE)
======================================================================
                 Port Name    Region  Total Ships  Waiting/Idle  Waiting Tankers  Waiting Cargo  Avg Speed (kts)  Congestion %
           Port of Tallinn   Estonia           46            46                6             13              0.0        100.0%
          Port of Helsinki   Finland           47            43                0              4              0.6         91.5%
      Port of Kotka-Hamina   Finland           15            15                0              7              0.0        100.0%
           Port of Vysotsk    Baltic           11            11                1              2              0.2        100.0%
          Port of Primorsk    Baltic           10             5                3              0              2.8         50.0%
         Port of Stockholm    Sweden            8             2                0              0              6.7         25.0%
```

---

## 🛠️ Tech Stack & Engineering Decisions

| Component | Technology | Engineering Justification |
| :--- | :--- | :--- |
| **Engine / OLAP** | **DuckDB 2.0 + Spatial** | Zero-cloud-cost embedded analytical powerhouse. Executes spatial joins over millions of points without needing an expensive PostGIS instance or heavy Spark cluster. |
| **Ingestion** | **Python 3 / Requests / REST** | Lightweight, robust, with built-in retry logic and UTF-8 safe telemetry streaming. |
| **Data Quality** | **Pytest + SQL Assertions** | Automated unit tests enforcing domain constraints (e.g. ITU-R AIS speed error filtering, coordinate boundaries). |
| **Serving & BI** | **Streamlit + PyDeck** | GPU-accelerated 3D MapGL geospatial rendering with vessel classification and live metric drill-downs. |
| **CI/CD** | **GitHub Actions** | Automated end-to-end continuous integration running ingestion, transformation, and tests on every commit. |

---

## 🚀 Quickstart: Run in 60 Seconds

### 1. Clone the repository:
```bash
git clone https://github.com/your-username/aegis-maritime-lakehouse.git
cd aegis-maritime-lakehouse
```

### 2. Install dependencies:
```bash
pip install -r requirements.txt
```

### 3. Run the complete pipeline & launch dashboard:
```bash
python run_pipeline.py
```
*This command fetches live AIS data, runs spatial models in DuckDB, passes all quality tests, and launches the 3D map in your browser at `http://localhost:8501`!*

---

## 🧪 Running Automated Tests

To run the data quality test suite:
```bash
pytest tests/ -v
```

Output:
```text
tests/test_pipeline.py::test_lakehouse_raw_telemetry_exists PASSED    [ 25%]
tests/test_pipeline.py::test_sensor_error_filtered_in_silver PASSED   [ 50%]
tests/test_pipeline.py::test_port_geofences_validity PASSED          [ 75%]
tests/test_pipeline.py::test_gold_congestion_marts PASSED           [100%]
============================== 4 passed in 3.98s ==============================
```

---

## 📂 Repository Structure

```text
aegis-maritime-lakehouse/
├── .github/
│   └── workflows/
│       └── ci.yml                    # Automated GitHub Actions CI workflow
├── data/
│   └── lakehouse/
│       └── maritime_lakehouse.duckdb # Embedded DuckDB database with Spatial indices
├── ingest_engine/
│   └── ingest.py                     # Real-time AIS telemetry & vessel metadata ingestion
├── models/
│   └── spatial_analysis.py           # Spatial SQL geofencing, distance calculation & marts
├── dashboard/
│   └── app.py                        # Streamlit + PyDeck 3D interactive intelligence dashboard
├── tests/
│   └── test_pipeline.py              # Automated data quality & schema contract tests
├── requirements.txt                  # Python dependencies
├── run_pipeline.py                   # Master single-command pipeline orchestrator
└── README.md                         # Project documentation and engineering case study
```

---

## 📜 License
MIT License. Open source research and engineering.
