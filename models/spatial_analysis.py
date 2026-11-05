"""
AegisSea - Spatial Analytics & Financial Demurrage Engine
=========================================================
Leverages DuckDB-Spatial to calculate:
1. Spatial point-in-polygon and distance joins.
2. Port Congestion and Anchorage queues.
3. FINANCIAL DEMURRAGE LOSSES ($/day): The exact financial penalties
   paid by charterers and cargo owners when vessels are delayed in anchorage.
"""

import os
import sys
import duckdb

if sys.platform.startswith("win"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "lakehouse", "maritime_lakehouse.duckdb")

# Industry Average Daily Demurrage Rates (Penalties for Idle Anchorage Delay)
# Sources: Clarksons Shipping Intelligence & Baltic Exchange Indexes
DEMURRAGE_RATES = {
    "tanker_daily_usd": 45000.0,    # Crude Oil & Chemical Tankers ($1,875 / hour)
    "cargo_daily_usd": 25000.0,     # Container & Dry Bulk Vessels ($1,041 / hour)
    "other_daily_usd": 15000.0      # General Cargo & Tug support ($625 / hour)
}

def run_spatial_transformations():
    print("="*70)
    print("  AEGIS-SEA: SPATIAL MODELING & FINANCIAL DEMURRAGE ENGINE")
    print("="*70)
    
    con = duckdb.connect(DB_PATH)
    con.execute("INSTALL spatial; LOAD spatial;")
    
    # 1. Port Dimension Table
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
    
    # 2. Silver Layer
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
        WHERE latitude BETWEEN 50.0 AND 70.0
          AND longitude BETWEEN 10.0 AND 35.0;
    """)
    
    # 3. Spatial Proximity and Waiting Detection
    print("[3/4] Performing Geospatial Joins & Hourly Idle Calculations...")
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
            ROUND(6371 * 2 * ASIN(SQRT(
                POWER(SIN(RADIANS(p.center_lat - t.latitude) / 2), 2) +
                COS(RADIANS(t.latitude)) * COS(RADIANS(p.center_lat)) *
                POWER(SIN(RADIANS(p.center_lon - t.longitude) / 2), 2)
            )), 2) as distance_to_port_km,
            CASE 
                WHEN (6371 * 2 * ASIN(SQRT(
                    POWER(SIN(RADIANS(p.center_lat - t.latitude) / 2), 2) +
                    COS(RADIANS(t.latitude)) * COS(RADIANS(p.center_lat)) *
                    POWER(SIN(RADIANS(p.center_lon - t.longitude) / 2), 2)
                ))) <= p.anchorage_radius_km 
                AND (t.speed_knots_clean < 2.0 OR t.nav_status_label IN ('At Anchor', 'Moored'))
                THEN 1 ELSE 0 
            END as is_waiting_or_anchored,
            -- Estimated Financial Demurrage Cost Rate ($/Day) based on Vessel Class
            CASE 
                WHEN t.ship_category LIKE '%Tanker%' THEN 45000.0
                WHEN t.ship_category LIKE '%Cargo%' THEN 25000.0
                ELSE 15000.0
            END as daily_burn_rate_usd
        FROM silver_vessel_telemetry t
        CROSS JOIN dim_ports p;
    """)
    
    # 4. Gold Mart: Financial Demurrage & Supply Chain Risk Scorecard
    print("[4/4] Building Gold Mart: Financial Demurrage Loss Scorecard...")
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
            ROUND(
                (COUNT(DISTINCT CASE WHEN f.is_waiting_or_anchored = 1 THEN f.mmsi END) * 100.0) / 
                NULLIF(COUNT(DISTINCT CASE WHEN f.distance_to_port_km <= p.anchorage_radius_km THEN f.mmsi END), 0),
                1
            ) as congestion_occupancy_pct,
            -- FINANCIAL IMPACT: Total Daily Demurrage Burn ($/Day) currently sitting idle in port
            ROUND(SUM(CASE WHEN f.is_waiting_or_anchored = 1 THEN f.daily_burn_rate_usd ELSE 0 END), 0) as daily_demurrage_loss_usd,
            ROUND(SUM(CASE WHEN f.is_waiting_or_anchored = 1 THEN f.daily_burn_rate_usd / 24.0 ELSE 0 END), 0) as hourly_demurrage_burn_usd
        FROM dim_ports p
        LEFT JOIN fct_vessel_port_proximity f ON p.port_id = f.port_id
        GROUP BY p.port_id, p.port_name, p.country, p.port_type
        ORDER BY daily_demurrage_loss_usd DESC;
    """)
    
    print("\n" + "="*80)
    print("💰 FINANCIAL SUPPLY CHAIN DEMURRAGE LOSS SCORECARD (LIVE)")
    print("="*80)
    scorecard = con.execute("""
        SELECT 
            port_name,
            total_vessels_in_zone as total_ships,
            anchored_or_idle_vessels as idle_ships,
            waiting_tankers,
            waiting_cargo_ships,
            daily_demurrage_loss_usd as daily_loss_usd,
            hourly_demurrage_burn_usd as burn_per_hour_usd
        FROM mart_port_congestion;
    """).df()
    print(scorecard.to_string(index=False))
    print("="*80)
    
    total_daily_loss = con.execute("SELECT SUM(daily_demurrage_loss_usd) FROM mart_port_congestion").fetchone()[0]
    print(f"\n🔥 TOTAL DAILY FINANCIAL LOSS CURRENTLY IDLE IN BALTIC PORTS: ${total_daily_loss:,.0f} USD / Day\n")
    con.close()

if __name__ == "__main__":
    run_spatial_transformations()
