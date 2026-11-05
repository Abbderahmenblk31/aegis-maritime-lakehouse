"""
AegisSea - Maritime Telemetry Ingestion Engine
==============================================
Ingests 100% genuine real-time AIS vessel locations and metadata from
the National Maritime Open Feeds (Baltic & Scandinavian Waters).
Stores raw pings into DuckDB Lakehouse with Spatial indexing.
"""

import sys
import os
import requests
import duckdb
import pandas as pd
from datetime import datetime, timezone

# Ensure stdout handles UTF-8 on Windows
if sys.platform.startswith("win"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
LAKEHOUSE_DIR = os.path.join(BASE_DIR, "data", "lakehouse")
os.makedirs(DATA_RAW_DIR, exist_ok=True)
os.makedirs(LAKEHOUSE_DIR, exist_ok=True)

LOCATIONS_URL = "https://meri.digitraffic.fi/api/ais/v1/locations"
VESSELS_URL = "https://meri.digitraffic.fi/api/ais/v1/vessels"
HEADERS = {"User-Agent": "AegisSea-Maritime-Lakehouse/1.0 (Open-Data-Research)"}

# Ship Type Mapping according to ITU/IMO AIS standards
SHIP_TYPE_MAPPING = {
    0: "Not Available",
    20: "Wing In Ground (WIG)",
    30: "Fishing",
    31: "Towing",
    32: "Towing (Large)",
    33: "Dredger / Underwater Ops",
    34: "Diving Ops",
    35: "Military Ops",
    36: "Sailing Vessel",
    37: "Pleasure Craft",
    40: "High Speed Craft (HSC)",
    50: "Pilot Vessel",
    51: "Search and Rescue (SAR)",
    52: "Tug",
    53: "Port Tender",
    54: "Anti-Pollution Equipment",
    55: "Law Enforcement",
    58: "Medical Transport",
    60: "Passenger Ferry / Cruise",
    70: "Cargo / Container Ship",
    80: "Tanker (Oil / Chemicals / Gas)",
    90: "Other / Unspecified"
}

def resolve_ship_category(ship_type_id):
    """Maps granular AIS ship types to primary business categories."""
    if not ship_type_id:
        return "Unknown"
    type_group = (ship_type_id // 10) * 10
    if type_group in SHIP_TYPE_MAPPING:
        return SHIP_TYPE_MAPPING[type_group]
    return f"Type-{ship_type_id}"

def fetch_live_vessels_metadata():
    """Fetches real-time vessel static and voyage data."""
    print("[1/3] Fetching vessel metadata (Names, Types, Destinations)...")
    resp = requests.get(VESSELS_URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    vessels = resp.json()
    print(f"   -> Retrieved metadata for {len(vessels)} registered commercial vessels.")
    
    meta_dict = {}
    for v in vessels:
        mmsi = v.get("mmsi")
        if not mmsi:
            continue
        ship_type_code = v.get("shipType", 0)
        draught_meters = (v.get("draught", 0) or 0) / 10.0 # AIS reports draught in 1/10 meters
        length_meters = (v.get("referencePointA", 0) or 0) + (v.get("referencePointB", 0) or 0)
        width_meters = (v.get("referencePointC", 0) or 0) + (v.get("referencePointD", 0) or 0)
        
        meta_dict[mmsi] = {
            "vessel_name": (v.get("name") or "UNKNOWN").strip(),
            "call_sign": (v.get("callSign") or "").strip(),
            "imo_number": v.get("imo"),
            "ship_type_code": ship_type_code,
            "ship_category": resolve_ship_category(ship_type_code),
            "draught_m": round(draught_meters, 1),
            "length_m": length_meters,
            "width_m": width_meters,
            "destination": (v.get("destination") or "UNSPECIFIED").strip().upper()
        }
    return meta_dict

def fetch_live_telemetry():
    """Fetches real-time GPS locations and dynamics for all vessels."""
    print("[2/3] Fetching live AIS telemetry pings from Baltic & European Waters...")
    resp = requests.get(LOCATIONS_URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    payload = resp.json()
    features = payload.get("features", [])
    print(f"   -> Captured {len(features)} active vessel position pings.")
    return features

def process_and_persist(telemetry_features, metadata_dict):
    """Combines telemetry with vessel intelligence and writes to DuckDB Lakehouse."""
    print("[3/3] Processing, transforming, and persisting to Data Lakehouse...")
    now_utc = datetime.now(timezone.utc)
    records = []
    
    for f in telemetry_features:
        props = f.get("properties", {})
        geom = f.get("geometry", {})
        coords = geom.get("coordinates", [None, None])
        lon, lat = coords[0], coords[1]
        
        if lat is None or lon is None or lat == 0 or lon == 0:
            continue
            
        mmsi = props.get("mmsi")
        meta = metadata_dict.get(mmsi, {})
        
        sog_knots = props.get("sog", 0.0) # Speed over ground in knots
        cog_degrees = props.get("cog", 0.0) # Course over ground in degrees
        heading = props.get("heading", 0)
        nav_status_code = props.get("navStat", -1)
        
        nav_status_label = "Under Way"
        if nav_status_code == 1:
            nav_status_label = "At Anchor"
        elif nav_status_code == 5:
            nav_status_label = "Moored"
        elif nav_status_code == 0:
            nav_status_label = "Under Way Using Engine"
        elif nav_status_code in (2, 3):
            nav_status_label = "Restricted Maneuverability"
            
        records.append({
            "ingestion_timestamp": now_utc,
            "mmsi": int(mmsi),
            "vessel_name": meta.get("vessel_name", "UNKNOWN"),
            "ship_category": meta.get("ship_category", "Unknown"),
            "destination": meta.get("destination", "UNSPECIFIED"),
            "draught_m": float(meta.get("draught_m", 0.0)),
            "length_m": int(meta.get("length_m", 0)),
            "width_m": int(meta.get("width_m", 0)),
            "latitude": float(lat),
            "longitude": float(lon),
            "speed_knots": float(sog_knots),
            "course_deg": float(cog_degrees),
            "heading_deg": int(heading),
            "nav_status_code": int(nav_status_code),
            "nav_status_label": nav_status_label
        })
    
    db_path = os.path.join(LAKEHOUSE_DIR, "maritime_lakehouse.duckdb")
    con = duckdb.connect(db_path)
    
    con.execute("INSTALL spatial; LOAD spatial;")
    
    df = pd.DataFrame(records)
    con.register("df_incoming_pings", df)
    
    con.execute("""
        CREATE TABLE IF NOT EXISTS raw_ais_telemetry AS 
        SELECT 
            *,
            ST_Point(longitude, latitude) as geom_point
        FROM df_incoming_pings
        WHERE 1=0;
    """)
    
    con.execute("""
        INSERT INTO raw_ais_telemetry 
        SELECT 
            *,
            ST_Point(longitude, latitude) as geom_point
        FROM df_incoming_pings;
    """)
    
    total_count = con.execute("SELECT COUNT(*) FROM raw_ais_telemetry").fetchone()[0]
    unique_vessels = con.execute("SELECT COUNT(DISTINCT mmsi) FROM raw_ais_telemetry").fetchone()[0]
    
    print("\n" + "="*70)
    print("SUCCESS: LAKEHOUSE INGESTION COMPLETED!")
    print(f"   * Database: {db_path}")
    print(f"   * Total Telemetry Records in Lakehouse: {total_count:,}")
    print(f"   * Unique Commercial Vessels Tracked:   {unique_vessels:,}")
    print("="*70)
    
    print("\n[+] Top 5 Fastest Live Vessels Tracked Right Now:")
    sample_df = con.execute("""
        SELECT 
            vessel_name, 
            ship_category, 
            speed_knots, 
            destination, 
            round(latitude, 4) as lat, 
            round(longitude, 4) as lon, 
            nav_status_label
        FROM raw_ais_telemetry
        WHERE vessel_name != 'UNKNOWN'
        ORDER BY speed_knots DESC
        LIMIT 5;
    """).df()
    print(sample_df.to_string(index=False))
    print("\n")
    con.close()

if __name__ == "__main__":
    print("="*70)
    print("  AEGIS-SEA: REAL-TIME MARITIME INGESTION ENGINE")
    print("="*70)
    meta = fetch_live_vessels_metadata()
    pings = fetch_live_telemetry()
    process_and_persist(pings, meta)
