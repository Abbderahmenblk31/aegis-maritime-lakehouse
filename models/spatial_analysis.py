"""
AegisSea - Spatial Analytics & Port Congestion Engine
====================================================
Leverages DuckDB-Spatial to execute spatial point-in-polygon and distance
joins between real AIS vessel GPS coordinates and major European maritime ports.
Calculates Port Congestion, Anchorage Waiting, and Fleet Distribution.
"""

import os
import sys
import duckdb

if sys.platform.startswith("win"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "lakehouse", "maritime_lakehouse.duckdb")

def run_spatial_transformations():
    print("="*70)
    print("  AEGIS-SEA: SPATIAL MODELING & PORT BOTTLENECK ENGINE")
    print("="*70)
    
    con = duckdb.connect(DB_PATH)
    con.execute("INSTALL spatial; LOAD spatial;")
    
    # 1. Create Reference Dimension Table of Major Baltic / European Ports
    print("[1/4] Constructing Port Geofence Dimension Table...")
    con.execute("""
        CREATE OR REPLACE TABLE dim_ports (
            port_id VARCHAR PRIMARY KEY,
            port_name VARCHAR,
            country VARCHAR,
            port_type VARCHAR,
            center_lat DOUBLE,
            center_lon DOUBLE,
            anchorage_radius_km DOUBLE
        );
        
        DELETE FROM dim_ports;
        INSERT INTO dim_ports VALUES
            ('HEL', 'Port of Helsinki', 'Finland', 'Commercial & Passenger Hub', 60.155, 24.955, 12.0),
            ('TLL', 'Port of Tallinn', 'Estonia', 'Cargo & Passenger Ferry', 59.445, 24.760, 10.0),
            ('KOT', 'Port of Kotka-Hamina', 'Finland', 'Largest Nordic Export Terminal', 60.450, 26.950, 15.0),
            ('PRM', 'Port of Primorsk', 'Baltic Sea', 'Major Crude Oil Export Terminal', 60.350, 28.620, 18.0),
            ('VYS', 'Port of Vysotsk', 'Baltic Sea', 'LNG & Coal Hub', 60.620, 28.560, 12.0),
            ('SPB', 'Big Port of St. Petersburg', 'Baltic Sea', 'Container & Bulk Gateway', 59.880, 30.220, 20.0),
            ('STK', 'Port of Stockholm', 'Sweden', 'Passenger & Ro-Ro Hub', 59.330, 18.110, 12.0);
    """)
    print("   -> Created 7 European strategic port geofence zones.")
    
    # 2. Build Cleansed Silver Layer with Real Maritime Domain Rules
    print("[2/4] Engineering Silver Layer: Cleansing telemetry & anomalies...")
    con.execute("""
        CREATE OR REPLACE VIEW silver_vessel_telemetry AS
        SELECT 
            ingestion_timestamp,
            mmsi,
            vessel_name,
            ship_category,
            destination,
            draught_m,
            length_m,
            width_m,
            latitude,
            longitude,
            -- Data Quality Rule: AIS 102.3 knots indicates sensor fault / speed not available
            CASE 
                WHEN speed_knots >= 102.2 THEN NULL 
                ELSE speed_knots 
            END as speed_knots_clean,
            course_deg,
            heading_deg,
            nav_status_code,
            nav_status_label,
            geom_point
        FROM raw_ais_telemetry
        WHERE latitude BETWEEN 50.0 AND 70.0  -- Baltic & North Sea bounding coordinates
          AND longitude BETWEEN 10.0 AND 35.0;
    """)
    print("   -> Applied maritime domain rules (sensor error filtering & spatial bounding).")
    
    # 3. Spatial Join: Point-in-Radius calculation between Vessels and Ports
    print("[3/4] Performing Geospatial Distance Calculations (Spatial SQL)...")
    con.execute("""
        CREATE OR REPLACE TABLE fct_vessel_port_proximity AS
        SELECT 
            t.mmsi,
            t.vessel_name,
            t.ship_category,
            t.destination,
            t.draught_m,
            t.speed_knots_clean as current_speed_knots,
            t.nav_status_label,
            p.port_id,
            p.port_name,
            p.country,
            p.anchorage_radius_km,
            -- Spherical distance calculation in kilometers (Haversine formula in pure SQL)
            ROUND(6371 * 2 * ASIN(SQRT(
                POWER(SIN(RADIANS(p.center_lat - t.latitude) / 2), 2) +
                COS(RADIANS(t.latitude)) * COS(RADIANS(p.center_lat)) *
                POWER(SIN(RADIANS(p.center_lon - t.longitude) / 2), 2)
            )), 2) as distance_to_port_km,
            -- Detection of vessels in Anchorage / Waiting status
            CASE 
                WHEN (6371 * 2 * ASIN(SQRT(
                    POWER(SIN(RADIANS(p.center_lat - t.latitude) / 2), 2) +
                    COS(RADIANS(t.latitude)) * COS(RADIANS(p.center_lat)) *
                    POWER(SIN(RADIANS(p.center_lon - t.longitude) / 2), 2)
                ))) <= p.anchorage_radius_km 
                AND (t.speed_knots_clean < 2.0 OR t.nav_status_label IN ('At Anchor', 'Moored'))
                THEN 1 ELSE 0 
            END as is_waiting_or_anchored
        FROM silver_vessel_telemetry t
        CROSS JOIN dim_ports p;
    """)
    
    # 4. Port Congestion Analytics Mart (Gold Layer)
    print("[4/4] Building Gold Mart: Port Congestion Scorecard & Bottleneck Index...")
    con.execute("""
        CREATE OR REPLACE TABLE mart_port_congestion AS
        SELECT 
            p.port_id,
            p.port_name,
            p.country,
            p.port_type,
            COUNT(DISTINCT CASE WHEN f.distance_to_port_km <= p.anchorage_radius_km THEN f.mmsi END) as total_vessels_in_zone,
            COUNT(DISTINCT CASE WHEN f.is_waiting_or_anchored = 1 THEN f.mmsi END) as anchored_or_idle_vessels,
            COUNT(DISTINCT CASE WHEN f.is_waiting_or_anchored = 1 AND f.ship_category LIKE '%Tanker%' THEN f.mmsi END) as waiting_tankers,
            COUNT(DISTINCT CASE WHEN f.is_waiting_or_anchored = 1 AND f.ship_category LIKE '%Cargo%' THEN f.mmsi END) as waiting_cargo_ships,
            ROUND(AVG(CASE WHEN f.distance_to_port_km <= p.anchorage_radius_km AND f.current_speed_knots IS NOT NULL THEN f.current_speed_knots END), 1) as avg_speed_in_zone_knots,
            -- Congestion Risk Formula (Anchored ratio & absolute queue depth)
            ROUND(
                (COUNT(DISTINCT CASE WHEN f.is_waiting_or_anchored = 1 THEN f.mmsi END) * 100.0) / 
                NULLIF(COUNT(DISTINCT CASE WHEN f.distance_to_port_km <= p.anchorage_radius_km THEN f.mmsi END), 0),
                1
            ) as congestion_occupancy_pct
        FROM dim_ports p
        LEFT JOIN fct_vessel_port_proximity f ON p.port_id = f.port_id
        GROUP BY p.port_id, p.port_name, p.country, p.port_type
        ORDER BY anchored_or_idle_vessels DESC;
    """)
    
    print("\n" + "="*70)
    print("PORT CONGESTION & SUPPLY CHAIN BOTTLENECK SCORECARD (LIVE)")
    print("="*70)
    scorecard = con.execute("""
        SELECT 
            port_name,
            country,
            total_vessels_in_zone as total_ships,
            anchored_or_idle_vessels as waiting_idle,
            waiting_tankers,
            waiting_cargo_ships,
            avg_speed_in_zone_knots as avg_speed,
            congestion_occupancy_pct as congestion_pct
        FROM mart_port_congestion;
    """).df()
    print(scorecard.to_string(index=False))
    print("="*70)
    
    # 5. Display real vessels currently anchored at ports
    print("\n[+] Sample Vessels Currently Queuing / Anchored in Port Zones:")
    queuing_vessels = con.execute("""
        SELECT 
            vessel_name,
            ship_category,
            port_name,
            destination,
            distance_to_port_km,
            current_speed_knots,
            nav_status_label
        FROM fct_vessel_port_proximity
        WHERE is_waiting_or_anchored = 1 AND vessel_name != 'UNKNOWN'
        ORDER BY distance_to_port_km ASC
        LIMIT 6;
    """).df()
    print(queuing_vessels.to_string(index=False))
    print("\n")
    con.close()

if __name__ == "__main__":
    run_spatial_transformations()
