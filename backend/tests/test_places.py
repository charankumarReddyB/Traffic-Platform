import os, tempfile
os.environ.setdefault("TRAFFIC_DB", os.path.join(tempfile.mkdtemp(), "pl.db")); os.environ.setdefault("ADMIN_EMAIL", "boss@x.com"); os.environ.setdefault("ADMIN_PASSWORD", "adminpass1")
from fastapi.testclient import TestClient
import main
c = TestClient(main.app)
H = lambda: {"x-token": c.post("/api/login", json={"email": "boss@x.com", "password": "adminpass1"}).json()["token"]}
S = lambda q: c.get("/api/places/search", params={"q": q}, headers=H())

def test_local_search_and_validation():
    assert c.get("/api/places/search?q=city").status_code == 401 and S("a").status_code == 422
    r = S("hospital").json()["results"]; assert any(x["source"] == "hospital" and x["node"] in main.NODES for x in r)
    assert S("12").json()["results"][0]["node"] == 12 and S("999").json()["results"] == []
    with main.db() as cx: cx.execute("INSERT OR IGNORE INTO bus_stops(name,node) VALUES('Zeta Terminal',20)")
    assert any(x["source"] == "bus stop" and x["node"] == 20 for x in S("zeta").json()["results"])

def test_address_search_snaps_caches_and_falls_back(monkeypatch):
    calls = []; monkeypatch.setattr(main, "GRAPH", "openstreetmap")
    def fake(q): calls.append(q); return [{"display_name": "Test Road, Somewhere", "lat": "13.021", "lon": "80.221"}, {"display_name": "Far away", "lat": "50", "lon": "10"}, {"display_name": "Bad"}]
    monkeypatch.setattr(main, "geocode_remote", fake); main.GEO_CACHE.clear()
    r = S("test road").json(); addr = [x for x in r["results"] if x["source"] == "address"]
    assert len(addr) == 1 and addr[0]["node"] in main.NODES and r["geocoder_error"] is None         # outside-area and malformed hits dropped
    S("test road"); assert len(calls) == 1                                                            # second identical search served from cache
    def boom(q): raise OSError("no network")
    monkeypatch.setattr(main, "geocode_remote", boom); main.GEO_CACHE.clear(); r = S("hospital").json()
    assert r["geocoder_error"] and any(x["source"] == "hospital" for x in r["results"])               # local results survive a geocoder failure
    monkeypatch.setenv("GEOCODER", "off"); main.GEO_CACHE.clear(); assert S("hospital").json()["geocoder_error"] is None
