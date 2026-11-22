import os, tempfile
os.environ.setdefault("TRAFFIC_DB", os.path.join(tempfile.mkdtemp(), "s.db")); os.environ.setdefault("ADMIN_EMAIL", "boss@x.com"); os.environ.setdefault("ADMIN_PASSWORD", "adminpass1")
from fastapi.testclient import TestClient
import main
c = TestClient(main.app)
def tok(e, p): return c.post("/api/login", json={"email": e, "password": p}).json().get("token")
H = lambda t: {"x-token": t}
ADM = lambda: H(tok("boss@x.com", "adminpass1"))
def mk(email): return c.post("/api/admin/users", headers=ADM(), json=dict(name="Op", email=email, password="password1", role="bus_operator"))
def uid(email): return [u for u in c.get("/api/admin/users", headers=ADM()).json() if u["email"] == email.lower()][0]["id"]
RID = 2   # seeded route: junctions 12,18,19,20,21,22,23,17

def setup():
    mk("sch@x.com"); mk("sch2@x.com")
    assert c.post(f"/api/admin/bus-routes/{RID}/assign", headers=ADM(), json={"operator_id": uid("sch@x.com")}).status_code == 200
    return H(tok("sch@x.com", "password1")), H(tok("sch2@x.com", "password1"))

def test_stops_validation_and_analysis():
    a, b = setup()
    assert c.post(f"/api/bus/routes/{RID}/stops", headers=a, json={"stops": [{"name": "End", "node": 17}, {"name": "Depot", "node": 12}]}).status_code == 422   # wrong order
    assert c.post(f"/api/bus/routes/{RID}/stops", headers=a, json={"stops": [{"name": "X", "node": 0}, {"name": "Y", "node": 17}]}).status_code == 422       # not on route
    assert c.post(f"/api/bus/routes/{RID}/stops", headers=b, json={"stops": [{"name": "D", "node": 12}, {"name": "E", "node": 17}]}).status_code == 404       # other operator
    assert c.post(f"/api/bus/routes/{RID}/stops", headers=a, json={"stops": [{"name": "Depot", "node": 12}, {"name": "Mid", "node": 20}, {"name": "End", "node": 17}]}).status_code == 200
    r = c.get(f"/api/bus/routes/{RID}/analysis", headers=a).json()
    assert [s["stop"] for s in r["stops"]] == ["Depot", "Mid", "End"] and all(s["delay"] >= 0 for s in r["stops"]) and r["schedule_is_default"] and len(r["timetable"]) == 6
    assert c.get(f"/api/bus/routes/{RID}/analysis", headers=b).status_code == 404
    assert "Depot:12" in [x for x in c.get("/api/bus/routes", headers=a).json() if x["id"] == RID][0]["stops"]

def test_congestion_increases_trip_time_and_fleet_check():
    a, _b = setup(); base = c.get(f"/api/bus/routes/{RID}/analysis", headers=a).json()["trip_minutes"]
    for e in main.route_eids([12, 18, 19, 20, 21, 22, 23, 17]): c.post("/api/congestion", headers=ADM(), json={"edge_id": e, "congested": True})
    jam = c.get(f"/api/bus/routes/{RID}/analysis", headers=a).json(); c.post("/api/reset", headers=ADM())
    assert jam["trip_minutes"] > base and jam["needed"] >= jam["needed_free_flow"]

def test_schedule_proposal_review():
    a, b = setup()
    bad = dict(route_id=RID, first="08:00", last="07:00", headway_min=10, fleet=3)
    assert c.post("/api/bus/schedule-proposals", headers=a, json=bad).status_code == 422
    assert c.post("/api/bus/schedule-proposals", headers=a, json={**bad, "last": "20:00", "headway_min": 1}).status_code == 422
    assert c.post("/api/bus/schedule-proposals", headers=b, json={**bad, "last": "20:00"}).status_code == 403
    tight = c.post("/api/bus/schedule-proposals", headers=a, json={**bad, "last": "20:00", "headway_min": 2, "fleet": 1}); assert tight.status_code == 201 and tight.json()["short_by"] > 0
    ok = c.post("/api/bus/schedule-proposals", headers=a, json={**bad, "last": "20:00", "headway_min": 10, "fleet": 6}).json()
    assert c.post(f"/api/admin/proposals/{ok['id']}/decision", headers=a, json={"decision": "approved"}).status_code == 403
    assert "headway" in c.get("/api/bus/proposals", headers=a).json()[0]["summary"]
    assert c.post(f"/api/admin/proposals/{ok['id']}/decision", headers=ADM(), json={"decision": "approved"}).status_code == 200
    r = c.get(f"/api/bus/routes/{RID}/analysis", headers=a).json(); assert not r["schedule_is_default"] and r["headway"] == 10 and r["fleet"] == 6
    assert c.post(f"/api/admin/bus-routes/{RID}/schedule", headers=ADM(), json=dict(first="05:30", last="23:00", headway_min=12, fleet=5)).status_code == 200
