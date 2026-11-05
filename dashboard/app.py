"""
AegisSea - Maritime Intelligence & Port Observability Dashboard
===============================================================
A high-performance geospatial intelligence application built on top
of DuckDB Lakehouse and real-time live AIS telemetry feeds.
"""

import os
import duckdb
import streamlit as st
import pydeck as pdk
import pandas as pd

# Page Configuration
st.set_page_config(
    page_title="AegisSea | Maritime Intelligence Lakehouse",
    page_icon="🚢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "lakehouse", "maritime_lakehouse.duckdb")

@st.cache_data(ttl=60)
def load_lakehouse_data():
    """Queries DuckDB Lakehouse for live spatial models and congestion marts."""
    con = duckdb.connect(DB_PATH, read_only=True)
    con.execute("INSTALL spatial; LOAD spatial;")
    
    # Live vessels with cleaned speeds and spatial coordinates
    vessels_df = con.execute("""
        SELECT 
            mmsi,
            vessel_name,
            ship_category,
            destination,
            draught_m,
            length_m,
            latitude,
            longitude,
            speed_knots_clean as speed_knots,
            course_deg,
            nav_status_label
        FROM silver_vessel_telemetry
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL;
    """).df()
    
    # Port Congestion Scorecard
    congestion_df = con.execute("SELECT * FROM mart_port_congestion ORDER BY anchored_or_idle_vessels DESC;").df()
    
    # Strategic Ports Dimensions
    ports_df = con.execute("SELECT * FROM dim_ports;").df()
    
    con.close()
    return vessels_df, congestion_df, ports_df

# Title and Header
st.markdown("""
<div style='background-color: #0e1e2d; padding: 20px; border-radius: 10px; margin-bottom: 25px; border-left: 6px solid #00bcd4;'>
    <h1 style='color: #ffffff; margin: 0; font-size: 28px;'>🚢 AegisSea: Maritime Telemetry & Port Congestion Lakehouse</h1>
    <p style='color: #a0aec0; margin: 5px 0 0 0; font-size: 14px;'>
        Real-Time Geospatial AIS Telemetry Pipeline | DuckDB Spatial Engine | European Supply Chain Intelligence
    </p>
</div>
""", unsafe_allow_html=True)

try:
    vessels_df, congestion_df, ports_df = load_lakehouse_data()
except Exception as e:
    st.error(f"Failed to connect to DuckDB Lakehouse: {e}")
    st.info("Please ensure you have executed `python ingest_engine/ingest.py` and `python models/spatial_analysis.py` first.")
    st.stop()

# Color mapping for vessels by type
def assign_color(cat):
    if "Tanker" in cat:
        return [239, 68, 68, 200]    # Red: Oil & Gas Tankers
    elif "Cargo" in cat:
        return [59, 130, 246, 200]   # Blue: Container & Cargo
    elif "Passenger" in cat:
        return [16, 185, 129, 200]   # Green: Ferry & Cruise
    elif "Pilot" in cat or "Tug" in cat:
        return [245, 158, 11, 200]   # Amber: Tugs & Operations
    return [156, 163, 175, 160]      # Gray: Others

vessels_df["color"] = vessels_df["ship_category"].apply(assign_color)

# Top KPI Metric Cards
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("📡 Live Tracked Vessels", f"{len(vessels_df):,}", delta="100% Real AIS Data")
with col2:
    total_waiting = int(congestion_df["anchored_or_idle_vessels"].sum())
    st.metric("⚓ Vessels in Anchorage / Idle", f"{total_waiting:,}", delta=f"{int(congestion_df['waiting_tankers'].sum())} Tankers Waiting", delta_color="inverse")
with col3:
    highest_congestion_port = congestion_df.iloc[0]["port_name"]
    st.metric("🚨 Most Congested Port Zone", highest_congestion_port, f"{congestion_df.iloc[0]['total_vessels_in_zone']} Vessels In-Zone")
with col4:
    active_cargo = len(vessels_df[vessels_df["ship_category"].str.contains("Cargo", na=False)])
    st.metric("📦 Active Cargo / Containers", f"{active_cargo:,}", delta="Under Transit")

st.markdown("---")

# Main Layout: 3D Map + Analytics Scorecard
tab1, tab2, tab3 = st.tabs(["🗺️ Live 3D Geospatial Map", "📊 Port Congestion Scorecard", "🔍 Vessel Deep Inspector"])

with tab1:
    st.subheader("Live Vessel Telemetry & Port Geofences")
    st.caption("🔴 Red = Tankers | 🔵 Blue = Cargo / Containers | 🟢 Green = Passenger | 🟡 Amber = Tug / Pilots")
    
    # Vessels Scatter Layer
    vessel_layer = pdk.Layer(
        "ScatterplotLayer",
        data=vessels_df,
        get_position=["longitude", "latitude"],
        get_color="color",
        get_radius=1800,
        pickable=True,
        auto_highlight=True,
    )
    
    # Port Geofence Layer (Circle buffers)
    port_layer = pdk.Layer(
        "ScatterplotLayer",
        data=ports_df,
        get_position=["center_lon", "center_lat"],
        get_color=[0, 188, 212, 60],
        get_line_color=[0, 188, 212, 255],
        line_width_min_pixels=2,
        stroked=True,
        get_radius="anchorage_radius_km * 1000",
        pickable=True,
    )
    
    view_state = pdk.ViewState(
        latitude=59.8,
        longitude=25.0,
        zoom=6.0,
        pitch=35
    )
    
    deck = pdk.Deck(
        layers=[port_layer, vessel_layer],
        initial_view_state=view_state,
        tooltip={
            "html": "<b>Vessel:</b> {vessel_name}<br/>"
                    "<b>Type:</b> {ship_category}<br/>"
                    "<b>Speed:</b> {speed_knots} kts<br/>"
                    "<b>Destination:</b> {destination}<br/>"
                    "<b>Status:</b> {nav_status_label}",
            "style": {"backgroundColor": "#1a202c", "color": "#ffffff"}
        },
        map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
    )
    st.pydeck_chart(deck, use_container_width=True)

with tab2:
    st.subheader("Supply Chain Bottlenecks & Port Waiting Times")
    st.dataframe(
        congestion_df[[
            "port_name", "country", "total_vessels_in_zone", "anchored_or_idle_vessels",
            "waiting_tankers", "waiting_cargo_ships", "avg_speed_in_zone_knots", "congestion_occupancy_pct"
        ]].rename(columns={
            "port_name": "Port Name",
            "country": "Region",
            "total_vessels_in_zone": "Total Ships in Zone",
            "anchored_or_idle_vessels": "Anchored / Idle",
            "waiting_tankers": "Waiting Tankers",
            "waiting_cargo_ships": "Waiting Cargo",
            "avg_speed_in_zone_knots": "Avg Speed (kts)",
            "congestion_occupancy_pct": "Congestion %"
        }),
        use_container_width=True
    )
    
    # Bar Chart of Waiting Ships by Port
    st.bar_chart(
        data=congestion_df.set_index("port_name")[["waiting_cargo_ships", "waiting_tankers"]],
        color=["#3b82f6", "#ef4444"]
    )

with tab3:
    st.subheader("Vessel Fleet Telemetry Browser")
    selected_category = st.selectbox("Filter by Vessel Category:", ["All"] + sorted(list(vessels_df["ship_category"].unique())))
    
    filtered_df = vessels_df if selected_category == "All" else vessels_df[vessels_df["ship_category"] == selected_category]
    
    st.dataframe(
        filtered_df[[
            "mmsi", "vessel_name", "ship_category", "speed_knots", "destination",
            "draught_m", "length_m", "nav_status_label", "latitude", "longitude"
        ]].sort_values(by="speed_knots", ascending=False),
        use_container_width=True
    )

st.sidebar.title("⚓ Navigation & Controls")
st.sidebar.info("""
**Data Engine Specs:**
- **Source:** Real-Time European AIS Feeds
- **Lakehouse:** DuckDB with Spatial Extension
- **Refresh Interval:** Every 60s
- **Telemetry Type:** True GPS & Marine Transponders
""")

if st.sidebar.button("🔄 Trigger Pipeline Ingestion Now"):
    with st.spinner("Fetching latest live satellite & coastal AIS pings..."):
        import subprocess
        subprocess.run(["python", os.path.join(BASE_DIR, "ingest_engine", "ingest.py")], check=True)
        subprocess.run(["python", os.path.join(BASE_DIR, "models", "spatial_analysis.py")], check=True)
        st.cache_data.clear()
        st.success("Lakehouse successfully refreshed with live maritime signals!")
        st.rerun()
