"""Live TomTom Traffic Ingestion Verification Script.
Samples live TomTom Traffic Flow speeds for prioritized roads in Anna Nagar, Chennai,
logs observations to the database, and prints saved readings, timestamps, count, and data age.

Usage:
  # In PowerShell:
  $env:TRAFFIC_SOURCE = "live"
  $env:TOMTOM_API_KEY = "your_actual_key_here"
  python experiments/test_live_tomtom.py
"""
import os, sys, time, sqlite3
from typing import Dict, Any

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import graph
import traffic

def test_live_ingestion():
    api_key = os.environ.get("TOMTOM_API_KEY", "").strip()
    source = os.environ.get("TRAFFIC_SOURCE", "simulated").lower()
    db_path = os.environ.get("TRAFFIC_DB", "traffic.db")

    print("=" * 70)
    print("LIVE TRAFFIC INGESTION VERIFICATION")
    print("=" * 70)
    print(f"Target Area: Anna Nagar, Chennai, India")
    print(f"Configured Mode: TRAFFIC_SOURCE={source}")
    print(f"TOMTOM_API_KEY Present: {bool(api_key)}")
    print(f"Database Target: {db_path}")
    print("-" * 70)

    if not api_key:
        print("[BLOCKED BY EVIDENCE RULE]: TOMTOM_API_KEY environment variable is not set.")
        print("To run live mode against TomTom Traffic Flow API:")
        print("  1. Obtain a free TomTom API key from developer.tomtom.com")
        print("  2. In your terminal, set: $env:TOMTOM_API_KEY='<your-api-key>'")
        print("  3. Set: $env:TRAFFIC_SOURCE='live'")
        print("  4. Rerun: python experiments/test_live_tomtom.py")
        print("-" * 70)
        return False

    # Initialize network & traffic manager
    net = graph.RoadNetwork("network.json")
    mgr = traffic.LiveTrafficManager(net)

    print(f"Loaded network: {len(net.nodes)} junctions, {len(net.edges)} road segments.")
    print("Initiating live TomTom Flow Segment API poll for top arterial links...")
    
    t0 = time.time()
    
    # Callback to log to database
    def log_cb(edge_id, cur_speed, free_speed, load_val, src_name):
        with sqlite3.connect(db_path) as cx:
            cx.execute(
                "INSERT INTO traffic_observations(road_id, observed_at, speed_kmh, free_speed_kmh, load, data_source) VALUES(?,?,?,?,?,?)",
                (edge_id, time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), cur_speed, free_speed, load_val, src_name)
            )

    status = mgr.refresh_live(db_log_callback=log_cb)
    elapsed = time.time() - t0

    print(f"Poll completed in {elapsed:.2f}s.")
    print(f"Manager Status: {status['label']}")
    print(f"Daily Quota Requests Used: {status['daily_requests_used']}/{status['daily_quota_limit']}")
    print(f"Live Roads Sampled: {status['live_roads']}")
    print(f"Data Age: {status['age_seconds']}s")

    if status.get("error"):
        print(f"Warning / Error: {status['error']}")

    # Query DB observations
    with sqlite3.connect(db_path) as cx:
        cx.row_factory = sqlite3.Row
        rows = cx.execute(
            "SELECT * FROM traffic_observations WHERE data_source LIKE '%tomtom%' OR data_source='live' ORDER BY id DESC LIMIT 15"
        ).fetchall()
        total_count = cx.execute(
            "SELECT COUNT(*) FROM traffic_observations WHERE data_source LIKE '%tomtom%' OR data_source='live'"
        ).fetchone()[0]

    print("\nSAVED DATABASE READINGS (traffic_observations table):")
    print(f"Total Live Observations in DB: {total_count}")
    if rows:
        print(f"{'Obs ID':<8} {'Road ID':<10} {'Observed At (UTC)':<22} {'Speed (km/h)':<14} {'Free Speed':<12} {'Load (V/C)':<12} {'Data Source'}")
        print("-" * 95)
        for r in rows:
            print(f"{r['id']:<8} #{r['road_id']:<9} {r['observed_at']:<22} {r['speed_kmh']:<14.1f} {r['free_speed_kmh']:<12.1f} {r['load']:<12.3f} {r['data_source']}")
    else:
        print("No live observations currently stored in DB.")

    print("=" * 70)
    return True

if __name__ == "__main__":
    test_live_ingestion()
