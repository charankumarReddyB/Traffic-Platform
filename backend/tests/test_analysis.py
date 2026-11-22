import os, tempfile
os.environ.setdefault("TRAFFIC_DB", os.path.join(tempfile.mkdtemp(), "a.db")); os.environ.setdefault("ADMIN_EMAIL", "boss@x.com"); os.environ.setdefault("ADMIN_PASSWORD", "adminpass1")
from fastapi.testclient import TestClient
import main
c = TestClient(main.app)
H = lambda: {"x-token": c.post("/api/login", json={"email": "boss@x.com", "password": "adminpass1"}).json()["token"]}

def test_curve_and_validation():
    assert c.get("/api/predict/curve?dow=1").status_code == 401
    r = c.get("/api/predict/curve?dow=1", headers=H()).json()
    assert len(r["hours"]) == len(r["random_forest"]) == len(r["baseline_hourly_mean"]) == 24 and all(0 <= x <= 2 for x in r["random_forest"])
    assert r["random_forest"][9] > r["random_forest"][3]                  # morning peak above the small hours in the synthetic model
    assert c.get("/api/predict/curve?dow=9", headers=H()).status_code == 422
    assert c.get("/api/predict?hour=99&dow=1", headers=H()).status_code == 422
    assert c.get("/analysis").status_code == 200
