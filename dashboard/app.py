"""
AegisSea - Maritime Intelligence & Financial Demurrage Dashboard
=================================================================
A geospatial & economic intelligence application built on DuckDB Lakehouse
and real-time AIS telemetry feeds. Translates port congestion into
actionable multi-million dollar supply chain financial analytics.
"""

import os
import sys
import duckdb
import streamlit as st
import pydeck as pdk
import pandas as pd
import plotly.graph_objects as go

# Page Configuration
st.set_page_config(
    page_title="AegisSea | Maritime Financial Intelligence",
    page_icon="🚢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "lakehouse", "maritime_lakehouse.duckdb")

@st.cache_data(ttl=60)
def load_lakehouse_data():
    if not os.path.exists(DB_PATH):
        import subprocess
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        subprocess.run([sys.executable, os.path.join(BASE_DIR, "ingest_engine", "ingest.py")], check=True)
        subprocess.run([sys.executable, os.path.join(BASE_DIR, "models", "spatial_analysis.py")], check=True)

    con = duckdb.connect(DB_PATH, read_only=True)
    try:
        con.execute("INSTALL spatial; LOAD spatial;")
    except Exception:
        pass
    
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
    
    congestion_df = con.execute("SELECT * FROM mart_port_congestion ORDER BY daily_demurrage_loss_usd DESC;").df()
    ports_df = con.execute("SELECT * FROM dim_ports;").df()
    
    try:
        rerouting_df = con.execute("SELECT * FROM mart_prescriptive_vessel_rerouting ORDER BY net_economic_savings_usd DESC;").df()
    except Exception:
        rerouting_df = pd.DataFrame()
        
    con.close()
    return vessels_df, congestion_df, ports_df, rerouting_df

# Title and Header
st.markdown("""
<div style='background-color: #0b1926; padding: 22px; border-radius: 12px; margin-bottom: 25px; border-left: 6px solid #ef4444;'>
    <div style='display: flex; justify-content: space-between; align-items: center;'>
        <div>
            <h1 style='color: #ffffff; margin: 0; font-size: 26px;'>🚢 AegisSea: Maritime Telemetry & Port Demurrage Lakehouse</h1>
            <p style='color: #94a3b8; margin: 6px 0 0 0; font-size: 14px;'>
                Translating Live AIS Transponders & Port Bottlenecks into <b>Real Financial Supply Chain Impact</b>
            </p>
        </div>
        <div style='background-color: #1e293b; padding: 10px 18px; border-radius: 8px; border: 1px solid #334155; text-align: right;'>
            <span style='color: #94a3b8; font-size: 12px;'>Engine:</span> <b style='color: #38bdf8;'>DuckDB Spatial</b> | 
            <span style='color: #94a3b8; font-size: 12px;'>Data:</span> <b style='color: #22c55e;'>100% Live Transponders</b>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

try:
    vessels_df, congestion_df, ports_df, rerouting_df = load_lakehouse_data()
except Exception as e:
    st.error(f"Lakehouse connection error: {e}")
    st.stop()

# Color mapping
def assign_color(cat):
    if "Tanker" in cat:
        return [239, 68, 68, 220]    # Red: Oil & Gas Tankers
    elif "Cargo" in cat:
        return [59, 130, 246, 220]   # Blue: Container & Cargo
    elif "Passenger" in cat:
        return [16, 185, 129, 220]   # Green: Ferry & Cruise
    elif "Pilot" in cat or "Tug" in cat:
        return [245, 158, 11, 220]   # Amber: Tugs & Support
    return [148, 163, 184, 180]      # Slate: Others

vessels_df["color"] = vessels_df["ship_category"].apply(assign_color)

# Executive Financial KPI Cards
total_daily_loss = float(congestion_df["daily_demurrage_loss_usd"].sum())
total_hourly_burn = float(congestion_df["hourly_demurrage_burn_usd"].sum())
total_idle_vessels = int(congestion_df["anchored_or_idle_vessels"].sum())
total_waiting_tankers = int(congestion_df["waiting_tankers"].sum())

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric(
        "🔥 Total Daily Demurrage Loss",
        f"${total_daily_loss:,.0f}",
        delta=f"-${total_hourly_burn:,.0f} / Hour Burn",
        delta_color="inverse"
    )
with col2:
    st.metric(
        "⚓ Vessels Stuck in Queue / Anchorage",
        f"{total_idle_vessels:,} Ships",
        delta=f"{total_waiting_tankers} High-Value Tankers Delayed",
        delta_color="inverse"
    )
with col3:
    worst_port = congestion_df.iloc[0]["port_name"]
    worst_loss = congestion_df.iloc[0]["daily_demurrage_loss_usd"]
    st.metric(
        "🚨 Highest Cost Bottleneck",
        worst_port,
        delta=f"${worst_loss:,.0f} Daily Waste"
    )
with col4:
    st.metric(
        "📡 Live Tracked Fleet",
        f"{len(vessels_df):,} Vessels",
        delta="Baltic & North Sea Corridors"
    )

st.markdown("---")

# Navigation Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "💰 Financial Demurrage Analysis",
    "🗺️ 3D Geospatial Fleet & Port Map",
    "🔍 Vessel Cost & Fleet Inspector",
    "🤖 Prescriptive Vessel Rerouting Optimizer"
])

with tab1:
    st.subheader("Financial Penalty Breakdown: The Cost of Port Delay")
    st.markdown("""
    When container ships and oil tankers wait in anchorage, charterers pay **Demurrage Fees** 
    *(Standard charter rates: **$45,000/day** for Crude/Chemical Tankers, **$25,000/day** for Container Vessels)*.
    This table calculates the actual capital waste occurring in ports right now:
    """)
    
    st.dataframe(
        congestion_df[[
            "port_name", "country", "total_vessels_in_zone", "anchored_or_idle_vessels",
            "waiting_tankers", "waiting_cargo_ships", "daily_demurrage_loss_usd", "hourly_demurrage_burn_usd"
        ]].rename(columns={
            "port_name": "Port Hub",
            "country": "Region",
            "total_vessels_in_zone": "Total Ships in Zone",
            "anchored_or_idle_vessels": "Idle / Waiting Ships",
            "waiting_tankers": "Waiting Tankers ($45k/day)",
            "waiting_cargo_ships": "Waiting Cargo ($25k/day)",
            "daily_demurrage_loss_usd": "Est. Daily Demurrage ($)",
            "hourly_demurrage_burn_usd": "Burn Rate ($/Hour)"
        }),
        use_container_width=True
    )
    
    st.subheader("Daily Financial Waste by Port Hub ($ USD)")
    st.bar_chart(
        data=congestion_df.set_index("port_name")["daily_demurrage_loss_usd"],
        color="#ef4444"
    )

with tab2:
    st.subheader("Live 3D Vessel Telemetry & Strategic Geofence Polygons")
    st.caption("🔴 Red = Oil/Gas Tankers ($45k/d penalty) | 🔵 Blue = Cargo Containers ($25k/d) | 🟢 Green = Passenger | 🟡 Amber = Pilot/Tug")
    
    vessel_layer = pdk.Layer(
        "ScatterplotLayer",
        data=vessels_df,
        get_position=["longitude", "latitude"],
        get_color="color",
        get_radius=2000,
        pickable=True,
        auto_highlight=True,
    )
    
    port_layer = pdk.Layer(
        "ScatterplotLayer",
        data=ports_df,
        get_position=["center_lon", "center_lat"],
        get_color=[239, 68, 68, 40],
        get_line_color=[239, 68, 68, 255],
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
            "style": {"backgroundColor": "#0f172a", "color": "#f8fafc"}
        },
        map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
    )
    st.pydeck_chart(deck, use_container_width=True)

with tab3:
    st.subheader("Commercial Fleet Cost Profiler")
    
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        cat_filter = st.selectbox("Filter Vessel Class:", ["All"] + sorted(list(vessels_df["ship_category"].unique())))
    with col_f2:
        status_filter = st.selectbox("Filter Status:", ["All"] + sorted(list(vessels_df["nav_status_label"].unique())))
        
    filtered = vessels_df.copy()
    if cat_filter != "All":
        filtered = filtered[filtered["ship_category"] == cat_filter]
    if status_filter != "All":
        filtered = filtered[filtered["nav_status_label"] == status_filter]
        
    st.dataframe(
        filtered[[
            "mmsi", "vessel_name", "ship_category", "speed_knots", "destination",
            "draught_m", "length_m", "nav_status_label", "latitude", "longitude"
        ]].sort_values(by="speed_knots", ascending=False),
        use_container_width=True
    )

with tab4:
    st.subheader("🤖 Prescriptive Decision Intelligence: Vessel Rerouting & Demurrage Mitigation")
    st.caption("Physics & economic optimization comparing Port Demurrage Waiting Costs vs Bunker Fuel Transit Burn ($650/MT VLSFO).")
    
    if not rerouting_df.empty:
        total_potential_savings = float(rerouting_df["net_economic_savings_usd"].clip(lower=0).sum())
        total_divert_actions = int((rerouting_df["prescriptive_action"] == "🚨 DIVERT TO ALTERNATE PORT").sum())
        total_slow_steaming = int((rerouting_df["prescriptive_action"] == "⚠️ SLOW STEAMING DIRECTIVE").sum())
        
        rc1, rc2, rc3, rc4 = st.columns(4)
        rc1.metric("Net Economic Capital Saved", f"${total_potential_savings:,.0f} USD", delta="Demurrage Penalty Avoided", delta_color="normal")
        rc2.metric("Recommended Port Diversions", f"{total_divert_actions} Vessels", delta="High Queue Avoidance", delta_color="normal")
        rc3.metric("Slow Steaming Advisories", f"{total_slow_steaming} Vessels", delta="Fuel Conservation Mode")
        rc4.metric("Benchmark Bunker Fuel Rate", "$650 / MT", delta="VLSFO Marine Standard")
        
        # Action filter
        action_filter = st.radio("Filter Prescriptive Action Category:", ["All Decisions", "🚨 Divert Only", "⚠️ Slow Steaming Only"], horizontal=True)
        display_df = rerouting_df.copy()
        if action_filter == "🚨 Divert Only":
            display_df = display_df[display_df["prescriptive_action"] == "🚨 DIVERT TO ALTERNATE PORT"]
        elif action_filter == "⚠️ Slow Steaming Only":
            display_df = display_df[display_df["prescriptive_action"] == "⚠️ SLOW STEAMING DIRECTIVE"]
            
        st.markdown("### 📋 Prescriptive Voyage Re-routing Matrix")
        st.dataframe(
            display_df[[
                "vessel_name", "ship_category", "current_port_name", "current_port_queue",
                "optimal_diversion_port", "alt_port_queue", "dist_to_alt_port_km",
                "diversion_fuel_cost_usd", "projected_current_demurrage_usd",
                "net_economic_savings_usd", "prescriptive_action", "decision_rationale"
            ]].rename(columns={
                "vessel_name": "Vessel Name",
                "ship_category": "Vessel Class",
                "current_port_name": "Current Bottleneck",
                "current_port_queue": "Current Queue",
                "optimal_diversion_port": "Recommended Terminal",
                "alt_port_queue": "Target Queue",
                "dist_to_alt_port_km": "Transit Dist (km)",
                "diversion_fuel_cost_usd": "Bunker Fuel Cost ($)",
                "projected_current_demurrage_usd": "Gross Demurrage ($)",
                "net_economic_savings_usd": "Net Savings ($)",
                "prescriptive_action": "Prescriptive Action",
                "decision_rationale": "Automated Decision Intelligence Rationale"
            }),
            use_container_width=True
        )
        
        # Cost-Benefit Chart for Top 10 Divert Opportunities
        st.markdown("### 📊 Top 10 Economic Diversion Opportunities (Demurrage Avoidance vs Fuel Burn)")
        top_divert = rerouting_df.head(10)
        
        fig_divert = go.Figure()
        fig_divert.add_trace(go.Bar(
            x=top_divert["vessel_name"],
            y=top_divert["projected_current_demurrage_usd"],
            name="Projected Demurrage Delay Penalty ($)",
            marker_color="#ef4444"
        ))
        fig_divert.add_trace(go.Bar(
            x=top_divert["vessel_name"],
            y=top_divert["diversion_fuel_cost_usd"],
            name="Diversion Bunker Fuel Cost ($)",
            marker_color="#f59e0b"
        ))
        fig_divert.add_trace(go.Bar(
            x=top_divert["vessel_name"],
            y=top_divert["net_economic_savings_usd"],
            name="Net Capital Saved ($)",
            marker_color="#10b981"
        ))
        fig_divert.update_layout(
            barmode="group",
            template="plotly_dark",
            height=450,
            xaxis_title="Vessel",
            yaxis_title="USD ($)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_divert, use_container_width=True)
    else:
        st.info("Prescriptive rerouting optimizer initializing. Please click 'Trigger Live Telemetry Fetch'.")

st.sidebar.title("⚓ Pipeline Operations")
st.sidebar.markdown(f"""
- **Active Lakehouse:** DuckDB Spatial
- **Total Fleet:** `{len(vessels_df):,}` Ships
- **Daily Loss Rate:** `${total_daily_loss:,.0f}`
""")

if st.sidebar.button("🔄 Trigger Live Telemetry Fetch & Calculation"):
    with st.spinner("Streaming latest live AIS transponders & calculating demurrage..."):
        import subprocess
        subprocess.run(["python", os.path.join(BASE_DIR, "ingest_engine", "ingest.py")], check=True)
        subprocess.run(["python", os.path.join(BASE_DIR, "models", "spatial_analysis.py")], check=True)
        st.cache_data.clear()
        st.success("Refreshed with real live maritime signals!")
        st.rerun()
