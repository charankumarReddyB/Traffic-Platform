import os, tempfile
os.environ.setdefault("TRAFFIC_DB", os.path.join(tempfile.mkdtemp(), "p.db")); os.environ.setdefault("ADMIN_EMAIL", "boss@x.com"); os.environ.setdefault("ADMIN_PASSWORD", "adminpass1")
from fastapi.testclient import TestClient
import main
c = TestClient(main.app)
def tok(e, p): return c.post("/api/login", json={"email": e, "password": p}).json().get("token")
H = lambda t: {"x-token": t}
ADM = lambda: H(tok("boss@x.com", "adminpass1"))
def reg(email, role=None): return c.post("/api/register", json=dict(name="Req", email=email, password="password1", request_role=role))
def uid(email): return [u for u in c.get("/api/admin/users", headers=ADM()).json() if u["email"] == email.lower()][0]["id"]

def test_pages_served():
    for p in ("/", "/app", "/pending", "/history", "/login", "/register", "/map", "/route-compare", "/traffic-prediction", "/transit-planning", "/scenarios", "/reports", "/ambulance-dashboard", "/bus-dashboard", "/admin-dashboard"):
        assert c.get(p).status_code == 200
    assert "Sign in or register" in c.get("/").text

def test_role_request_flow_and_privilege_safety():
    assert reg("bad@x.com", "admin").status_code == 422                       # cannot even request admin
    assert reg("r1@x.com", "ambulance").status_code == 201
    l = c.post("/api/login", json=dict(email="r1@x.com", password="password1")).json(); assert l["role"] == "user" and l["request_status"] == "pending"
    t = H(l["token"]); assert c.post("/api/emergency/start", headers=t, json=dict(hospital_id=1, src=0)).status_code == 403   # a pending request grants nothing
    assert c.get("/api/admin/requests", headers=t).status_code == 403
    assert any(r["email"] == "r1@x.com" for r in c.get("/api/admin/requests", headers=ADM()).json())
    u = uid("r1@x.com")
    assert c.post(f"/api/admin/requests/{u}/decision", headers=ADM(), json={"decision": "approve"}).status_code == 422    # ambulance needs a code
    assert c.post(f"/api/admin/requests/{u}/decision", headers=ADM(), json={"decision": "approve", "amb_code": "AMB-R1"}).status_code == 200
    assert c.get("/api/me", headers=t).json()["role"] == "ambulance"
    ok = c.post("/api/emergency/start", headers=t, json=dict(hospital_id=1, src=0)); assert ok.status_code == 200
    assert c.get("/api/emergency/trips", headers=t).json()[0]["positions"] == 0
    c.post(f"/api/emergency/{ok.json()['trip_id']}/finish", headers=t, json={"status": "Cancelled"})

def test_role_request_reject_and_duplicate_code():
    reg("r2@x.com", "bus_operator"); reg("r3@x.com", "ambulance"); reg("r4@x.com", "ambulance")
    assert c.post(f"/api/admin/requests/{uid('r2@x.com')}/decision", headers=ADM(), json={"decision": "reject"}).status_code == 200
    me = c.get("/api/me", headers=H(tok("r2@x.com", "password1"))).json(); assert me["role"] == "user" and me["request_status"] == "rejected"
    assert c.post(f"/api/admin/requests/{uid('r3@x.com')}/decision", headers=ADM(), json={"decision": "approve", "amb_code": "AMB-D"}).status_code == 200
    assert c.post(f"/api/admin/requests/{uid('r4@x.com')}/decision", headers=ADM(), json={"decision": "approve", "amb_code": "AMB-D"}).status_code == 409
    assert c.post(f"/api/admin/requests/{uid('r3@x.com')}/decision", headers=ADM(), json={"decision": "reject"}).status_code == 404   # already decided
