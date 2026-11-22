import os, sys, json, subprocess, tempfile, textwrap
os.environ.setdefault("TRAFFIC_DB", os.path.join(tempfile.mkdtemp(), "l.db"))
import main

def test_speed_to_load_matches_bpr():
    x = main.speed_to_load(20, 40); assert abs((1 + 0.15 * x ** 4) - 2.0) < 0.01     # half speed -> double travel time
    assert main.speed_to_load(40, 40) == 0 and main.speed_to_load(50, 40) == 0

def test_live_refresh_overrides_model_and_logs(monkeypatch):
    monkeypatch.setenv("TRAFFIC_SOURCE", "live"); monkeypatch.setenv("TOMTOM_API_KEY", "k"); monkeypatch.setenv("LIVE_MAX_EDGES", "5")
    monkeypatch.setattr(main, "fetch_flow", lambda lat, lon: (10.0, 40.0))          # FAKE provider response (no network in tests)
    with main.db() as c: before = c.execute("SELECT COUNT(*) FROM traffic_observations").fetchone()[0]
    main.LIVE["at"] = 0; L = main.loads()
    assert len(main.LIVE["loads"]) == 5 and all(L[i] > 1.0 for i in main.LIVE["loads"]) and "LIVE traffic on 5" in main.traffic_status()["label"]
    with main.db() as c: assert c.execute("SELECT COUNT(*) FROM traffic_observations").fetchone()[0] - before == 5

def test_live_failure_falls_back_to_simulated(monkeypatch):
    monkeypatch.setenv("TRAFFIC_SOURCE", "live"); monkeypatch.setenv("TOMTOM_API_KEY", "k")
    def boom(lat, lon): raise OSError("no network")
    monkeypatch.setattr(main, "fetch_flow", boom); main.LIVE["at"] = 0; main.loads()
    st = main.traffic_status(); assert st["live_roads"] == 0 and "SIMULATED" in st["label"]
    monkeypatch.delenv("TOMTOM_API_KEY"); main.LIVE["at"] = 0; main.loads(); assert main.LIVE["error"] == "TOMTOM_API_KEY not set"

def test_real_graph_file_loads_and_routes():
    d = tempfile.mkdtemp(); f = os.path.join(d, "net.json")
    json.dump(dict(nodes={"0": [13.0, 80.2], "1": [13.0, 80.21], "2": [13.01, 80.21], "3": [13.01, 80.2]},
                   edges=[[0, 1, 1.0, 40], [1, 2, 1.0, 40], [2, 3, 1.0, 40], [3, 0, 1.0, 40]], hospitals=[["Test Hospital", 2]]), open(f, "w"))
    code = "import main;p,e,x=main.search(0,2);print(main.GRAPH,len(main.NODES),main.HOSP[1][0],len(p),len(main.BUS))"
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env={**os.environ, "NETWORK_FILE": f, "TRAFFIC_DB": os.path.join(d, "g.db")}, cwd=os.path.dirname(main.__file__))
    assert r.stdout.split()[-5:-1] == ["openstreetmap", "4", "Test", "Hospital"] or "openstreetmap 4 Test Hospital 3" in r.stdout, r.stderr[-400:]
