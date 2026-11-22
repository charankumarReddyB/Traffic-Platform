import os, tempfile, datetime as dt, math, random
os.environ.setdefault("TRAFFIC_DB", os.path.join(tempfile.mkdtemp(), "h.db")); os.environ.setdefault("ADMIN_EMAIL", "boss@x.com"); os.environ.setdefault("ADMIN_PASSWORD", "adminpass1")
from fastapi.testclient import TestClient
import main
c = TestClient(main.app)
def tok(e, p): return c.post("/api/login", json={"email": e, "password": p}).json().get("token")
ADM = lambda: {"x-token": tok("boss@x.com", "adminpass1")}

def test_rate_limit_and_headers(monkeypatch):
    monkeypatch.setitem(main.RATE, "login", 3); main.HITS.clear()
    codes = [c.post("/api/login", json=dict(email="nobody@x.com", password="badpass12")).status_code for _ in range(5)]
    assert codes == [401, 401, 401, 429, 429]; main.HITS.clear()
    h = c.get("/api/health"); assert h.json()["ok"] and h.headers["x-content-type-options"] == "nosniff" and h.headers["x-frame-options"] == "DENY"

def test_retrain_on_live_observations(monkeypatch):
    assert c.post("/api/admin/retrain", headers={"x-token": ""}).status_code == 401
    monkeypatch.setenv("MIN_LIVE_OBS", "1000000"); assert c.post("/api/admin/retrain", headers=ADM()).status_code == 409   # not enough data
    # TEST FIXTURE: synthetic rows labelled like live ones, to exercise the pipeline only (not real traffic)
    random.seed(1); t0 = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    rows = [(r, (t0 + dt.timedelta(hours=h)).isoformat(), 30, 40, max(0, 0.8 * math.exp(-((h % 24 - 9) ** 2) / 6) + random.gauss(0, .03)), "tomtom_live") for r in range(5) for h in range(24 * 14)]
    with main.db() as cx: cx.executemany("INSERT INTO traffic_observations(road_id,observed_at,speed_kmh,free_speed_kmh,load,data_source) VALUES(?,?,?,?,?,?)", rows)
    monkeypatch.setenv("MIN_LIVE_OBS", "500"); r = c.post("/api/admin/retrain", headers=ADM()); assert r.status_code == 200
    j = r.json(); assert j["n_test"] == len(rows) - j["n_train"] and j["n_train"] == int(len(rows) * .8) and j["random_forest"]["MAE"] > 0
    assert c.get("/api/metrics", headers=ADM()).json()["live_retrained"]["n_train"] == j["n_train"]
