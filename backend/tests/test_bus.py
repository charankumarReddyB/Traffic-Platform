import os, tempfile
os.environ.setdefault("TRAFFIC_DB", os.path.join(tempfile.mkdtemp(), "b.db")); os.environ.setdefault("ADMIN_EMAIL", "boss@x.com"); os.environ.setdefault("ADMIN_PASSWORD", "adminpass1")
from fastapi.testclient import TestClient
import main
c = TestClient(main.app)
def tok(e, p): return c.post("/api/login", json={"email": e, "password": p}).json().get("token")
H = lambda t: {"x-token": t}
ADM = lambda: H(tok("boss@x.com", "adminpass1"))
def mk(role, email, code=None): return c.post("/api/admin/users", headers=ADM(), json=dict(name="Op", email=email, password="password1", role=role, amb_code=code))
def uid(email): return [u for u in c.get("/api/admin/users", headers=ADM()).json() if u["email"] == email.lower()][0]["id"]

def test_bus_assignment_proposal_review_flow():
    mk("bus_operator", "opA@x.com"); mk("bus_operator", "opB@x.com"); a, b = H(tok("opA@x.com", "password1")), H(tok("opB@x.com", "password1"))
    assert c.get("/api/bus/compare", headers=a).json() == {}                                   # nothing assigned yet
    assert c.post("/api/admin/bus-routes/1/assign", headers=ADM(), json={"operator_id": uid("opA@x.com")}).status_code == 200
    r = c.get("/api/bus/compare", headers=a).json(); assert len(r) == 1 and "congested_segments" in list(r.values())[0]
    assert c.post("/api/bus/proposals", headers=b, json=dict(route_id=1, nodes=[12, 13])).status_code == 403   # other operator cannot touch it
    assert c.post("/api/bus/proposals", headers=a, json=dict(route_id=1, nodes=[12, 17])).status_code == 422   # not connected by one road
    ok = c.post("/api/bus/proposals", headers=a, json=dict(route_id=1, nodes=[12, 13, 14, 15, 16, 17], note="same")); assert ok.status_code == 201
    assert c.post(f"/api/admin/proposals/{ok.json()['id']}/decision", headers=a, json={"decision": "approved"}).status_code == 403
    assert c.post(f"/api/admin/proposals/{ok.json()['id']}/decision", headers=ADM(), json={"decision": "approved"}).status_code == 200
    assert c.post(f"/api/admin/proposals/{ok.json()['id']}/decision", headers=ADM(), json={"decision": "approved"}).status_code == 404   # already decided
    assert c.get("/api/bus/proposals", headers=a).json()[0]["status"] == "approved"

def test_location_updates_and_reports():
    mk("ambulance", "ambX@x.com", "AMB-X"); mk("ambulance", "ambY@x.com", "AMB-Y"); x, y = H(tok("ambX@x.com", "password1")), H(tok("ambY@x.com", "password1"))
    t = c.post("/api/emergency/start", headers=x, json=dict(hospital_id=1, src=0, severity="urgent")).json()["trip_id"]
    assert c.post(f"/api/emergency/{t}/location", headers=x, json=dict(lat=13.0, lon=80.2)).status_code == 200
    assert c.post(f"/api/emergency/{t}/location", headers=x, json=dict(lat=999, lon=80.2)).status_code == 422
    assert c.post(f"/api/emergency/{t}/location", headers=y, json=dict(lat=13.0, lon=80.2)).status_code == 404
    assert len(c.get(f"/api/emergency/{t}/track", headers=x).json()) == 1 and c.get(f"/api/emergency/{t}/track", headers=y).status_code == 404
    assert c.get("/api/reports", headers=x).status_code == 403
    r = c.get("/api/reports", headers=ADM()).json(); assert r["trips"] and r["prediction"]["random_forest"]["MAE"] > 0
