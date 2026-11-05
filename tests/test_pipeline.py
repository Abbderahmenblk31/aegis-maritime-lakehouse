"""
AegisSea - Pipeline & Data Quality Tests
========================================
Automated regression tests to verify data contracts, spatial integrity,
and clean separation across lakehouse medallion layers.
"""

import os
import duckdb
import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "lakehouse", "maritime_lakehouse.duckdb")

@pytest.fixture
def db_conn():
    con = duckdb.connect(DB_PATH, read_only=True)
    con.execute("INSTALL spatial; LOAD spatial;")
    yield con
    con.close()

def test_lakehouse_raw_telemetry_exists(db_conn):
    """Verifies raw bronze table exists and contains real vessel pings."""
    count = db_conn.execute("SELECT COUNT(*) FROM raw_ais_telemetry").fetchone()[0]
    assert count > 0, "Bronze telemetry table is empty!"

def test_sensor_error_filtered_in_silver(db_conn):
    """Ensures ITU-R AIS speed error (>= 102.2 knots) is strictly sanitized to NULL."""
    invalid_speeds = db_conn.execute("""
        SELECT COUNT(*) 
        FROM silver_vessel_telemetry 
        WHERE speed_knots_clean >= 102.2
    """).fetchone()[0]
    assert invalid_speeds == 0, f"Found {invalid_speeds} uncleaned sensor error speeds in silver layer!"

def test_port_geofences_validity(db_conn):
    """Ensures all strategic port reference dimensions have valid GPS coordinates."""
    invalid_ports = db_conn.execute("""
        SELECT COUNT(*) 
        FROM dim_ports 
        WHERE center_lat NOT BETWEEN -90 AND 90 
           OR center_lon NOT BETWEEN -180 AND 180
           OR anchorage_radius_km <= 0
    """).fetchone()[0]
    assert invalid_ports == 0, "Found invalid port dimensions!"

def test_gold_congestion_marts(db_conn):
    """Verifies port congestion metrics are calculated without division-by-zero errors."""
    df = db_conn.execute("SELECT * FROM mart_port_congestion").df()
    assert len(df) > 0, "Port congestion mart is empty!"
    assert "congestion_occupancy_pct" in df.columns
    # Check that occupancy percentage is between 0 and 100 or null
    valid_pct = df["congestion_occupancy_pct"].dropna()
    assert (valid_pct >= 0).all() and (valid_pct <= 100).all()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
