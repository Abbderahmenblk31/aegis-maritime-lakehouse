"""
AegisSea - One-Click Pipeline Orchestrator
=========================================
Runs full end-to-end data pipeline:
1. Ingests live AIS telemetry from European Maritime Feeds
2. Executes spatial SQL models in DuckDB
3. Runs automated data tests
4. Opens the interactive 3D Streamlit Dashboard
"""

import subprocess
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def run_step(title, command):
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)
    result = subprocess.run(command, cwd=BASE_DIR)
    if result.returncode != 0:
        print(f"❌ Error encountered in: {title}")
        sys.exit(result.returncode)

if __name__ == "__main__":
    print("""
    ========================================================
       🚢 AEGIS-SEA: MARITIME TELEMETRY DATA LAKEHOUSE 🚢
    ========================================================
    """)
    run_step("STEP 1: INGESTING LIVE AIS TELEMETRY", [sys.executable, "ingest_engine/ingest.py"])
    run_step("STEP 2: RUNNING SPATIAL SQL & PORT CONGESTION MODELS", [sys.executable, "models/spatial_analysis.py"])
    run_step("STEP 3: EXECUTING AUTOMATED DATA TESTS", [sys.executable, "-m", "pytest", "tests/", "-v"])
    
    print("\n" + "="*70)
    print("  STEP 4: LAUNCHING 3D INTERACTIVE DASHBOARD")
    print("="*70)
    print("Opening Streamlit on http://localhost:8501 ...")
    subprocess.run([sys.executable, "-m", "streamlit", "run", "dashboard/app.py"], cwd=BASE_DIR)
