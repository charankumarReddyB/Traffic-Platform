import os, tempfile
os.environ["TRAFFIC_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
os.environ.update(ADMIN_EMAIL="boss@x.com", ADMIN_PASSWORD="adminpass1")
from fastapi.testclient import TestClient
import main
c = TestClient(main.app)
def tok(e, p):
    r = c.post("/api/login", json={"email": e, "password": p}); return r.json().get("token") if r.status_code == 200 else None
def H(t): return {"x-token": t}
ADM = lambda: H(tok("boss@x.com", "adminpass1"))
def mk(role, email, code=None):
    return c.post("/api/admin/users", headers=ADM(), json=dict(name="Op", email=email, password="password1", role=role, amb_code=code))

def test_register_login_role_cannot_be_chosen():
    r = c.post("/api/register", json=dict(name="Ann", email="ann@x.com", password="password1", role="admin")); assert r.status_code == 201
    assert c.post("/api/login", json=dict(email="ann@x.com", password="password1")).json()["role"] == "user"
    assert c.post("/api/register", json=dict(name="A", email="bad", password="password1")).status_code == 422
    assert c.post("/api/login", json=dict(email="ann@x.com", password="wrong")).status_code == 401
def test_unauthorized_blocked():
    assert c.get("/api/network").status_code == 401
    u = H(tok("ann@x.com", "password1"))
    assert c.get("/api/admin/users", headers=u).status_code == 403
    assert c.post("/api/emergency/start", headers=u, json=dict(hospital_id=1, src=0)).status_code == 403
    assert c.get("/api/bus/compare", headers=u).status_code == 403
def test_admin_creates_and_suspends_ambulance():
    assert mk("ambulance", "amb1@x.com", "AMB-001").status_code == 201
    assert mk("ambulance", "amb2@x.com", "AMB-001").status_code == 409
    t = H(tok("amb1@x.com", "password1")); assert t["x-token"]
    uid = [u for u in c.get("/api/admin/users", headers=ADM()).json() if u["email"] == "amb1@x.com"][0]["id"]
    c.post(f"/api/admin/users/{uid}/status", headers=ADM(), json={"status": "suspended"})
    assert c.get("/api/me", headers=t).status_code == 401 and tok("amb1@x.com", "password1") is None
    c.post(f"/api/admin/users/{uid}/status", headers=ADM(), json={"status": "active"})
def test_emergency_trip_lifecycle():
    t = H(tok("amb1@x.com", "password1"))
    assert c.post("/api/emergency/start", headers=t, json=dict(hospital_id=9, src=0)).status_code == 422
    assert c.post("/api/emergency/start", headers=t, json=dict(hospital_id=1, lat=50, lon=10)).status_code == 422   # GPS outside area -> use simulated
    r = c.post("/api/emergency/start", headers=t, json=dict(hospital_id=1, src=0)); assert r.status_code == 200 and r.json()["recommended"]["minutes"] > 0
    assert c.post("/api/emergency/start", headers=t, json=dict(hospital_id=1, src=0)).status_code == 409
    assert c.post(f"/api/emergency/{r.json()['trip_id']}/finish", headers=t, json={"status": "Completed"}).status_code == 200
    assert c.get("/api/emergency/trips", headers=t).json()[0]["status"] == "Completed"
    assert c.post("/api/emergency/start", headers=ADM(), json=dict(hospital_id=1, src=0)).status_code == 403   # admin cannot impersonate ambulance
def test_scenario_recalculation_and_bad_input():
    r = c.post("/api/scenario", headers=ADM(), json=dict(name="t", src=0, dst=35, edge_ids=[0, 1, 2, 3, 4], level=1.9)).json()
    assert r["delay_if_no_reroute"] >= 0 and r["rerouted"]["minutes"] <= r["same_route_after_change"]["minutes"]
    assert c.post("/api/scenario", headers=ADM(), json=dict(name="t", src=0, dst=99, edge_ids=[1], level=1)).status_code == 422
    assert c.post("/api/scenario", headers=ADM(), json=dict(name="t", src=0, dst=5, edge_ids=[999], level=1)).status_code == 422
def test_routing_known_network_and_bus_and_metrics():
    a = c.get("/api/route?src=0&dst=35&algo=astar", headers=ADM()).json(); d = c.get("/api/route?src=0&dst=35&algo=dijkstra", headers=ADM()).json()
    assert abs(a["minutes"] - d["minutes"]) < 1e-6          # A* (admissible heuristic) must match Dijkstra
    assert c.get("/api/route?src=0&dst=77", headers=ADM()).status_code == 422
    mk("bus_operator", "bus1@x.com"); b = H(tok("bus1@x.com", "password1"))
    uid = [u for u in c.get("/api/admin/users", headers=ADM()).json() if u["email"] == "bus1@x.com"][0]["id"]
    for rid in (1, 2): assert c.post(f"/api/admin/bus-routes/{rid}/assign", headers=ADM(), json={"operator_id": uid}).status_code == 200
    assert len(c.get("/api/bus/compare", headers=b).json()) == 2
    assert c.get("/api/metrics", headers=b).json()["random_forest"]["MAE"] < c.get("/api/metrics", headers=b).json()["baseline_hourly_mean"]["MAE"]

def test_severity_profiles():
    mk("ambulance", "amb3@x.com", "AMB-003"); t = H(tok("amb3@x.com", "password1"))
    c.post("/api/scenario", headers=ADM(), json=dict(name="s", src=0, dst=35, edge_ids=[0, 1, 2, 3, 4, 5], level=1.9))
    for e in range(40): c.post("/api/congestion", headers=ADM(), json=dict(edge_id=e, congested=True)) if e % 3 == 0 else None
    mins = {}
    for sev in ("routine", "urgent", "critical"):
        r = c.post("/api/emergency/start", headers=t, json=dict(hospital_id=1, src=0, severity=sev)); assert r.status_code == 200
        mins[sev] = r.json()["recommended"]["minutes"]; c.post(f"/api/emergency/{r.json()['trip_id']}/finish", headers=t, json={"status": "Completed"})
    assert mins["critical"] <= mins["urgent"] <= mins["routine"]
    assert c.post("/api/emergency/start", headers=t, json=dict(hospital_id=1, src=0, severity="bogus")).status_code == 422
    assert c.get("/api/emergency/trips", headers=t).json()[0]["severity"] == "critical"
