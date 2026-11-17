# 🚢 AegisSea: Maritime Telemetry, Demurrage & Prescriptive Rerouting Lakehouse

[![Live Demo](https://img.shields.io/badge/Live%20Demo-Streamlit%20Cloud-FF4B4B.svg?style=for-the-badge&logo=streamlit)](https://abbderahmenblk31-aegis-maritime-lakehouse-dashboardapp-rlrsjs.streamlit.app/)
[![Geospatial CI](https://github.com/Abbderahmenblk31/aegis-maritime-lakehouse/actions/workflows/ci.yml/badge.svg)](https://github.com/Abbderahmenblk31/aegis-maritime-lakehouse/actions)
[![Engine: DuckDB Spatial](https://img.shields.io/badge/Engine-DuckDB%20Spatial%20OLAP-yellow.svg)](https://duckdb.org/)
[![Data: 100% Real AIS Telemetry](https://img.shields.io/badge/Data-100%25%20Live%20AIS%20VHF%20Feeds-blue.svg)](https://www.digitraffic.fi/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> 🔗 **Interactive Cloud Application:** [Launch AegisSea Live Dashboard](https://abbderahmenblk31-aegis-maritime-lakehouse-dashboardapp-rlrsjs.streamlit.app/)

An enterprise-grade **Geospatial Data Engineering, Financial Supply Chain & Decision Intelligence Lakehouse**. AegisSea ingests **100% genuine live AIS (Automatic Identification System) vessel telemetry** across Northern European and Baltic shipping corridors, models spatial trajectories in an embedded **DuckDB Spatial Lakehouse**, calculates real-time **Financial Port Demurrage Penalties ($/day)**, and runs a **Prescriptive Vessel Rerouting Optimization Engine** that recommends economically optimal port diversions to save millions in idle delays.

---

## 📌 Executive Summary & Operational Problem

Global supply chain disruptions and port congestion cost charterers, cargo owners, and shipping operators over **$30 Billion annually** in demurrage penalties and wasted bunker fuel.

When commercial vessels (Crude Tankers, Container Ships, Dry Bulk) arrive at congested marine gateways, they are forced to wait in anchorage queues. Standard charter party contracts enforce severe daily demurrage penalty burn rates:
* **Crude Oil & Chemical Tankers:** **$45,000 / Day** ($1,875 / hour)
* **Container & Dry Bulk Vessels:** **$25,000 / Day** ($1,041 / hour)
* **General Cargo & Support Tugs:** **$15,000 / Day** ($625 / hour)

**AegisSea** bridges the gap between raw geospatial transponders and executive financial decisions:
1. **Zero Toy Data:** Direct streaming ingestion from national VHF coastal radio stations (Digitraffic Baltic & NOAA Marine Cadastre feeds).
2. **Embedded Geospatial Lakehouse:** Reconciles vessel telemetry, draught, and speed with strategic port geofences using DuckDB-Spatial.
3. **Prescriptive Decision Intelligence:** Evaluates trade-offs between **Anchorage Waiting Demurrage** vs. **Bunker Fuel Transit Burn** to prescribe whether a delayed vessel should divert to an alternate lower-congestion terminal.

---

## 🏛️ Medallion Architecture & System Design

```text
       [Live Open Maritime Transponder Stream]
      (Real-time AIS pings via National VHF Coastal Stations)
                                │
                                ▼
  ┌─────────────────────────────────────────────────────────────┐
  │                 BRONZE LAYER (RAW INGESTION)                │
  │  • fetch_live_telemetry() & fetch_live_vessels_metadata()   │
  │  • Captures MMSI, GPS Coordinates, SOG, COG, Draught, Dest  │
  │  • Raw Parquet / DuckDB table: raw_ais_telemetry            │
  └─────────────────────────────┬───────────────────────────────┘
                                │
                                ▼
  ┌─────────────────────────────────────────────────────────────┐
  │             SILVER LAYER (CLEANSING & QUALITY)              │
  │  • ITU-R M.1371 Sensor Error Sanitization (102.3 kts -> NULL)│
  │  • Spatial Bounding Box Filter (Baltic / North Sea 50-70° N)│
  │  • Navigational Status Mapping (Under Way, At Anchor, Moored│
  │  • Deduplicated latest vessel telemetry snapshots           │
  └─────────────────────────────┬───────────────────────────────┘
                                │
                                ▼
  ┌─────────────────────────────────────────────────────────────┐
  │             GOLD LAYER (SPATIAL ANALYTICAL MARTS)           │
  │  • dim_ports: Port coordinates, types, anchorage geofences  │
  │  • fct_vessel_port_proximity: Haversine distance & queues   │
  │  • mart_port_congestion: Occupancy %, Demurrage burn ($/day)│
  └─────────────────────────────┬───────────────────────────────┘
                                │
                                ▼
  ┌─────────────────────────────────────────────────────────────┐
  │     PRESCRIPTIVE DECISION INTELLIGENCE (OPTIMIZATION)       │
  │  • mart_prescriptive_vessel_rerouting:                      │
  │    - Alternate port candidate network routing               │
  │    - Fuel consumption modeling (VLSFO @ $650/MT)            │
  │    - Net Economic Savings = Demurrage Avoided - Fuel Cost   │
  │    - Action: DIVERT / SLOW STEAMING / MAINTAIN BERTH        │
  └─────────────────────────────┬───────────────────────────────┘
                                │
              ┌─────────────────┴─────────────────┐
              ▼                                   ▼
 ┌──────────────────────────────┐    ┌──────────────────────────────┐
 │  AUTOMATED PYTEST CONTRACTS  │    │  STREAMLIT 3D BI DASHBOARD   │
 │  • AIS sensor error tests    │    │  • PyDeck 3D WebGL Map       │
 │  • Spatial coordinate bounds │    │  • Demurrage Loss Scorecards │
 │  • Demurrage rate validation │    │  • Prescriptive Action Matrix│
 │  • Prescriptive PnL positive │    │  • Plotly Cost-Benefit Charts│
 └──────────────────────────────┘    └──────────────────────────────┘
```

---

## 🧮 Prescriptive Optimization Model: Demurrage vs. Bunker Fuel

The prescriptive rerouting engine models the multi-terminal cost-benefit optimization problem:

$$\text{Net Economic Savings} = \left(\Delta \text{Queue Delay Days} \times \text{Daily Demurrage Burn}\right) - \text{Diversion Bunker Fuel Cost}$$

Where:
* **Current Port Projected Delay (Days):** $D_{\text{curr}} = \frac{Q_{\text{curr}} \times 4.0\text{ hours}}{24}$ (based on average berth clearance rate).
* **Alternate Port Projected Delay (Days):** $D_{\text{alt}} = \frac{Q_{\text{alt}} \times 4.0\text{ hours}}{24}$.
* **Transit Distance ($NM$):** $Dist_{\text{NM}} = \frac{Dist_{\text{km}}}{1.852}$.
* **Diversion Fuel Cost ($ USD):** $C_{\text{fuel}} = Dist_{\text{NM}} \times \text{Fuel Burn Rate (MT/NM)} \times \$650/\text{MT (VLSFO Benchmark)}$.
  - Tankers: $0.08\text{ MT/NM}$ (~$52 / NM).
  - Container / Cargo: $0.05\text{ MT/NM}$ (~$32.5 / NM).

### Prescriptive Decision Rules:
| Condition | Prescriptive Directive | Actionable Rationale |
| :--- | :--- | :--- |
| $\text{Net Savings} > \$20,000$ | `🚨 DIVERT TO ALTERNATE PORT` | Demurrage avoidance drastically outweighs transit bunker fuel expense. |
| $Q_{\text{curr}} > 15 \text{ ships}$ & $\text{Net Savings} \le \$20,000$ | `⚠️ SLOW STEAMING DIRECTIVE` | Reduce speed to 9 knots to absorb bottleneck arrival delay and save fuel. |
| Port Queue Normal ($< 3\text{ ships}$) | `✅ MAINTAIN CURRENT BERTH` | Terminal transit cost exceeds queue delay penalty. Hold position. |

---

## 📊 Live Scorecard & Production Results

### 1. Financial Demurrage Loss Scorecard (Live Baltic Fleet)
```text
================================================================================
💰 FINANCIAL SUPPLY CHAIN DEMURRAGE LOSS SCORECARD (LIVE OBSERVATIONS)
================================================================================
                 Port Name  Total Ships  Idle Ships  Waiting Tankers  Waiting Cargo  Daily Loss ($)  Hourly Burn ($)
           Port of Tallinn           47          46                6             13      $3,985,000        $166,042
          Port of Helsinki           47          45                0              4      $2,785,000        $116,042
      Port of Kotka-Hamina           16          15                0              7      $1,180,000         $49,167
           Port of Vysotsk           11          11                1              2        $845,000         $35,208
          Port of Primorsk           10           5                3              0        $660,000         $27,500
         Port of Stockholm            8           2                0              0        $120,000          $5,000
Big Port of St. Petersburg            1           1                0              0         $60,000          $2,500
================================================================================
🔥 TOTAL FLEET DAILY DEMURRAGE LOSS SITTING IDLE: $9,635,000 USD / Day
```

### 2. Prescriptive Vessel Rerouting Output (Sample)
```text
Vessel Name   Class    Current Port     Queue  Recommended Terminal      Target Q  Fuel Cost ($)  Net Savings ($)  Prescriptive Action
-----------------------------------------------------------------------------------------------------------------------------------------
IKLA          Tanker   Port of Tallinn     46  Big Port of St. Petersburg       1         $8,594        +$328,906  🚨 DIVERT TO ALTERNATE PORT
RINA          Tanker   Port of Tallinn     46  Big Port of St. Petersburg       1         $8,781        +$328,719  🚨 DIVERT TO ALTERNATE PORT
NAFTA         Tanker   Port of Tallinn     46  Big Port of St. Petersburg       1         $8,786        +$328,714  🚨 DIVERT TO ALTERNATE PORT
LOTOS         Tanker   Port of Tallinn     46  Big Port of St. Petersburg       1         $8,791        +$328,709  🚨 DIVERT TO ALTERNATE PORT
RIX ELEONORA  Cargo    Port of Tallinn     46  Big Port of St. Petersburg       1         $5,484        +$182,016  🚨 DIVERT TO ALTERNATE PORT
-----------------------------------------------------------------------------------------------------------------------------------------
💡 TOTAL FLEET ECONOMIC POTENTIAL SAVINGS: $13,243,697 USD
```

---

## 🛠️ Tech Stack & Engineering Decisions

| Layer | Technology | Architectural Justification |
| :--- | :--- | :--- |
| **Storage & OLAP Engine** | **DuckDB 1.0+ Spatial** | Embedded columnar lakehouse with vectorized spatial execution. Computes point-in-radius distance joins across thousands of vessels in sub-seconds without heavy PostGIS or Spark cluster overhead. |
| **Ingestion Pipeline** | **Python 3 / Requests / PyArrow** | Resilient REST consumer connecting to live government AIS transponder endpoints with automatic schema mapping. |
| **Geospatial & Visualization** | **Streamlit + PyDeck (Deck.gl) + Plotly** | High-performance WebGL 3D vessel tracking layered with dynamic port geofence circles and grouped cost-benefit charts. |
| **Automated Testing** | **Pytest** | Continuous data quality tests enforcing sensor error sanitation, GPS boundaries, and prescriptive non-negative PnL. |
| **CI/CD** | **GitHub Actions** | Automated integration tests executing on every commit. |

---

## 🧪 Automated Data Quality & Pipeline Test Suite

The repository contains automated regression tests in `tests/test_pipeline.py`:
```bash
pytest tests/ -v
```

Execution output:
```text
tests/test_pipeline.py::test_lakehouse_raw_telemetry_exists PASSED       [ 20%]
tests/test_pipeline.py::test_sensor_error_filtered_in_silver PASSED      [ 40%]
tests/test_pipeline.py::test_port_geofences_validity PASSED              [ 60%]
tests/test_pipeline.py::test_gold_congestion_marts PASSED                [ 80%]
tests/test_pipeline.py::test_prescriptive_vessel_rerouting PASSED        [100%]
============================== 5 passed in 2.02s ==============================
```

---

## 🚀 Quickstart: Run Locally in 60 Seconds

### 1. Clone the repository
```bash
git clone https://github.com/Abbderahmenblk31/aegis-maritime-lakehouse.git
cd aegis-maritime-lakehouse
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the complete pipeline & launch dashboard
```bash
python run_pipeline.py
```
*This command executes live telemetry ingestion, spatial transformations in DuckDB, runs all automated pytest assertions, and opens the interactive dashboard at `http://localhost:8501`.*

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
│   └── spatial_analysis.py           # Spatial SQL geofencing, demurrage modeling & prescriptive rerouting
├── dashboard/
│   └── app.py                        # Streamlit + PyDeck 3D WebGL intelligence dashboard
├── tests/
│   └── test_pipeline.py              # Automated data quality & schema contract tests
├── requirements.txt                  # Python dependencies
├── run_pipeline.py                   # Master single-command pipeline orchestrator
└── README.md                         # Project documentation and engineering case study
```

---

## 📜 License
MIT License. Open source research and engineering.
