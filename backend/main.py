"""AI-Powered Urban Traffic, Public Transport and Emergency Route Optimization Platform.
Team 10 Capstone Project.
Target Area: Anna Nagar, Chennai, India (Real OpenStreetMap road network & hospitals).
Live Traffic Provider: TomTom Traffic Flow API (quota-managed).
"""
import os, sys, math, time, json, secrets, hashlib, heapq, urllib.request, urllib.parse, datetime as dt
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
from concurrent.futures import ThreadPoolExecutor

import numpy as np
from fastapi import FastAPI, Header, HTTPException, Depends, Query, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from sklearn.ensemble import RandomForestRegressor

app = FastAPI(title="AI-Powered Urban Traffic, Public Transport & Emergency Platform")
rng = np.random.default_rng(42)

# ---------- 1. Simulated road network & Real OpenStreetMap graph ----------
N, LAT0, LON0, STEP = 6, 13.00, 80.20, 0.01
NODES = {r * N + c: (round(LAT0 + r * STEP, 6), round(LON0 + c * STEP, 6)) for r in range(N) for c in range(N)}

def hav(a: int, b: int) -> float:
    (la1, lo1), (la2, lo2) = NODES[a], NODES[b]
    p = math.pi / 180.0
    h = math.sin((la2 - la1) * p / 2.0) ** 2 + math.cos(la1 * p) * math.cos(la2 * p) * math.sin((lo2 - lo1) * p / 2.0) ** 2
    return 12742.0 * math.asin(math.sqrt(max(0.0, min(1.0, h))))

EDGES, ADJ = {}, {n: [] for n in NODES}
for r in range(N):
    for c in range(N):
        a = r * N + c
        for b in ([a + 1] if c < N - 1 else []) + ([a + N] if r < N - 1 else []):
            arterial = (r in (2, 3) and b == a + 1) or (c in (2, 3) and b == a + N)
            eid = len(EDGES)
            EDGES[eid] = dict(
                id=eid, a=a, b=b, km=hav(a, b), speed=50.0 if arterial else 30.0,
                centrality=round(1.0 - (abs((NODES[a][0] + NODES[b][0]) / 2.0 - 13.025) + abs((NODES[a][1] + NODES[b][1]) / 2.0 - 80.225)) / 0.05, 4)
            )
            ADJ[a].append((b, eid))
            ADJ[b].append((a, eid))

VMAX = 50.0
BBOX = (LAT0, LON0, LAT0 + (N - 1) * STEP, LON0 + (N - 1) * STEP)
BASE_DIR = Path(__file__).resolve().parent
_env_net = os.environ.get("NETWORK_FILE")
if _env_net:
    NETWORK_FILE = _env_net
elif (BASE_DIR / "network.json").exists():
    NETWORK_FILE = str(BASE_DIR / "network.json")
elif (BASE_DIR.parent / "network.json").exists():
    NETWORK_FILE = str(BASE_DIR.parent / "network.json")
else:
    NETWORK_FILE = "network.json"
HOSP_FILE = None
GRAPH = "simulated-grid"

if os.path.exists(NETWORK_FILE) and NETWORK_FILE != "__grid_test_fixture__" and os.environ.get("USE_GRID_FIXTURE") != "1":
    try:
        _g = json.load(open(NETWORK_FILE, "r", encoding="utf-8"))
        GRAPH = "openstreetmap"
        NODES = {int(k): (float(v[0]), float(v[1])) for k, v in _g["nodes"].items()}
        EDGES, ADJ = {}, {n: [] for n in NODES}
        _cl = sum(v[0] for v in NODES.values()) / max(len(NODES), 1)
        _co = sum(v[1] for v in NODES.values()) / max(len(NODES), 1)
        _far = max(abs(v[0] - _cl) + abs(v[1] - _co) for v in NODES.values()) or 1.0
        for item in _g["edges"]:
            a, b, km, sp = item[0], item[1], float(item[2]), float(item[3])
            eid = len(EDGES)
            mid = [(NODES[a][k] + NODES[b][k]) / 2.0 for k in (0, 1)]
            cent = round(1.0 - (abs(mid[0] - _cl) + abs(mid[1] - _co)) / _far, 4)
            EDGES[eid] = dict(id=eid, a=a, b=b, km=km, speed=sp, centrality=cent)
            ADJ[a].append((b, eid))
            ADJ[b].append((a, eid))
        HOSP_FILE = {i + 1: (h[0], int(h[1])) for i, h in enumerate(_g.get("hospitals", [])[:4])}
        lats = [v[0] for v in NODES.values()]
        lons = [v[1] for v in NODES.values()]
        BBOX = (min(lats), min(lons), max(lats), max(lons))
    except Exception as ex:
        print("[network] OSM load fallback to grid:", ex)

WEEKS = 4 if GRAPH == "simulated-grid" else 2

def t_free(e: Dict[str, Any]) -> float:
    return e["km"] / e["speed"] * 60.0

# ASSUMPTION (configurable, not measured): an emergency vehicle loses less time in queues than a normal car.
BYPASS = {"critical": 0.5, "urgent": 0.25, "routine": 0.0}

def t_loaded(e: Dict[str, Any], x: float, b: float = 0.0) -> float:
    return t_free(e) * (1.0 + 0.15 * (x ** 4) * (1.0 - b))

# ---------- 2. Traffic Generator & ML Predictor ----------
def true_load(e: Dict[str, Any], hour: float, dow: int) -> float:
    peak = math.exp(-((hour - 9.0) ** 2) / 4.0) + math.exp(-((hour - 18.0) ** 2) / 4.0)
    wk = 0.55 if dow >= 5 else 1.0
    return float(np.clip(e["centrality"] * (0.25 + 0.95 * peak) * wk + rng.normal(0.0, 0.05), 0.0, 2.0))

def feats(e: Dict[str, Any], h: float, d: int) -> List[float]:
    return [e["id"], e["centrality"], e["km"], h, d, math.sin(h * math.pi / 12.0), math.cos(h * math.pi / 12.0), d >= 5]

rows = [(e["id"], h, d, wk) for e in EDGES.values() for wk in range(WEEKS) for d in range(7) for h in range(24)]
X = np.array([feats(EDGES[i], h, d) for i, h, d, w in rows], float)
y = np.array([true_load(EDGES[i], h, d) for i, h, d, w in rows])
train = np.array([w < WEEKS - 1 for *_, w in rows]) # chronological split: first (WEEKS-1) train, last test

rf = RandomForestRegressor(n_estimators=60, max_depth=12, random_state=0, n_jobs=1).fit(X[train], y[train])

base = {}
for (i, h, d, w), v in zip(np.array(rows)[train], y[train]):
    base.setdefault((int(i), int(h)), []).append(v)
base = {k: float(np.mean(v)) for k, v in base.items()}
glob_base = float(np.mean(y[train])) if len(y[train]) else 0.5

te = ~train
pr_rf = rf.predict(X[te])
pr_bl = np.array([base.get((int(i), int(h)), glob_base) for i, h, d, w in np.array(rows)[te]])

# Naive persistence baseline: Last observed value
rows_arr = np.array(rows)
last_map = {int(row[0]): float(val) for row, val in zip(rows_arr[train], y[train])}
pr_last = []
for row, actual_y in zip(rows_arr[te], y[te]):
    pr_last.append(last_map.get(int(row[0]), glob_base))
    last_map[int(row[0])] = float(actual_y)
pr_last = np.array(pr_last)

def calc_metrics(pred: np.ndarray, truth: np.ndarray) -> Dict[str, Any]:
    mae = float(np.mean(np.abs(pred - truth)))
    rmse = float(np.sqrt(np.mean((pred - truth) ** 2)))
    # 95% bootstrap confidence interval
    errs = np.abs(pred - truth)
    boot = [float(np.mean(rng.choice(errs, size=len(errs), replace=True))) for _ in range(500)]
    ci = [round(float(np.percentile(boot, 2.5)), 4), round(float(np.percentile(boot, 97.5)), 4)]
    return dict(MAE=round(mae, 4), RMSE=round(rmse, 4), MAE_95_CI=ci)

METRICS = {
    "random_forest": calc_metrics(pr_rf, y[te]),
    "baseline_hourly_mean": calc_metrics(pr_bl, y[te]),
    "baseline_last_observed": calc_metrics(pr_last, y[te]),
    "n_train": int(np.sum(train)),
    "n_test": int(np.sum(te)),
    "split": "Strict chronological split (weeks 0..N-2 train, week N-1 test; no future leakage)",
    "beats_hourly_mean": bool(np.mean(np.abs(pr_rf - y[te])) < np.mean(np.abs(pr_bl - y[te]))),
    "beats_last_observed": bool(np.mean(np.abs(pr_rf - y[te])) < np.mean(np.abs(pr_last - y[te]))),
    "note": "Evaluated on held-out simulated week; synthetic data shows method behaviour."
}

# ---------- 3. Live Traffic State ----------
def baseline_loads(hour: float = 9.0, dow: int = 1) -> Dict[int, float]:
    return {i: float(v) for i, v in zip(EDGES, rf.predict([feats(e, hour, dow) for e in EDGES.values()]))}

LOADS = baseline_loads()
OVERRIDES = set()
LIVE = dict(loads={}, at=0.0, error=None)

def source() -> str:
    return os.environ.get("TRAFFIC_SOURCE", "simulated").lower()

def fetch_flow(lat: float, lon: float) -> Tuple[float, float]:
    """TomTom Flow Segment Data API. Key read strictly from TOMTOM_API_KEY env var."""
    q = urllib.parse.urlencode({
        "point": f"{lat},{lon}",
        "key": os.environ.get("TOMTOM_API_KEY", ""),
        "unit": "KMPH"
    })
    req = urllib.request.Request(
        "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json?" + q,
        headers={"User-Agent": "UrbanTrafficPlatform/1.0"}
    )
    with urllib.request.urlopen(req, timeout=6) as r:
        d = json.load(r)["flowSegmentData"]
    return float(d["currentSpeed"]), float(d["freeFlowSpeed"])

def speed_to_load(cur: float, free: float) -> float:
    return 0.0 if cur >= free else float(np.clip(((free / max(cur, 1.0) - 1.0) / 0.15) ** 0.25, 0.0, 2.0))

def refresh_live():
    LIVE["at"] = time.time()
    if not os.environ.get("TOMTOM_API_KEY"):
        LIVE["error"] = "TOMTOM_API_KEY not set"
        LIVE["loads"] = {}
        return
    top = sorted(EDGES.values(), key=lambda e: -e["centrality"])[:int(os.environ.get("LIVE_MAX_EDGES", "15"))]
    def one(e):
        mid = [(NODES[e["a"]][k] + NODES[e["b"]][k]) / 2.0 for k in (0, 1)]
        try:
            cur, free = fetch_flow(*mid)
            return e["id"], cur, free, None
        except Exception as ex:
            return e["id"], 0.0, 0.0, str(ex)[:80]
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(one, top))
    ok = [r for r in res if r[3] is None]
    LIVE["loads"] = {i: speed_to_load(c, f) for i, c, f, _ in ok}
    LIVE["error"] = None if ok else (res[0][3] if res else "no roads")
    try:
        with db() as c:
            c.executemany(
                "INSERT INTO traffic_observations(road_id,observed_at,speed_kmh,free_speed_kmh,load,data_source) VALUES(?,?,?,?,?,'tomtom_live')",
                [(i, now(), cu, fr, LIVE["loads"][i]) for i, cu, fr, _ in ok]
            )
    except Exception:
        pass

def loads() -> Dict[int, float]:
    L = {i: (1.8 if i in OVERRIDES else v) for i, v in LOADS.items()}
    if source() == "live":
        if time.time() - LIVE["at"] > int(os.environ.get("LIVE_TTL_SECONDS", "600")):
            refresh_live()
        for i, v in LIVE["loads"].items():
            if i not in OVERRIDES:
                L[i] = v
    return L

def traffic_status() -> Dict[str, Any]:
    n = len(LIVE["loads"])
    age_sec = round(time.time() - LIVE["at"], 1) if LIVE["at"] else None
    if source() != "live":
        label = "SIMULATED traffic (not real-world data)"
    elif n:
        label = f"LIVE traffic on {n} of {len(EDGES)} roads ({age_sec}s ago; others modelled)"
    else:
        label = f"LIVE mode unavailable ({LIVE['error'] or 'not refreshed yet'}) - showing SIMULATED"
    return dict(
        mode=source(),
        live_roads=n,
        total_roads=len(EDGES),
        graph=GRAPH,
        label=label,
        data_age_seconds=age_sec,
        error=LIVE["error"],
        last_refresh=dt.datetime.fromtimestamp(LIVE["at"], dt.timezone.utc).isoformat(timespec="seconds") if LIVE["at"] else None,
        prediction_model="Random Forest trained on chronological split with baselines and confidence intervals"
    )

# ---------- 4. Routing: Dijkstra & A* ----------
def search(
    src: int,
    dst: int,
    algo: str = "astar",
    mode: str = "aware",
    L: Optional[Dict[int, float]] = None,
    b: float = 0.0,
    departure_hour: Optional[float] = None,
    dow: int = 1
) -> Tuple[List[int], List[int], int]:
    L = L or loads()
    if src not in NODES or dst not in NODES:
        raise HTTPException(422, "Unknown junction")
    if src == dst:
        return [src], [], 0

    hs = (lambda n: hav(n, dst)) if mode == "static" else (lambda n: hav(n, dst) / VMAX * 60.0)
    h = hs if algo == "astar" else (lambda n: 0.0)
    pq = [(h(src), src)]
    g = {src: 0.0}
    prev = {}
    seen = set()
    expanded = 0

    while pq:
        _, u = heapq.heappop(pq)
        if u in seen:
            continue
        seen.add(u)
        expanded += 1
        if u == dst:
            break
        for v, eid in ADJ[u]:
            edge = EDGES[eid]
            if mode == "static":
                edge_cost = edge["km"]
            elif departure_hour is not None:
                # Time-dependent predicted traffic based on arrival time at road
                arr_h = (departure_hour + g[u] / 60.0) % 24.0
                pred_load = float(rf.predict([feats(edge, arr_h, dow)])[0])
                edge_cost = t_loaded(edge, np.clip(pred_load, 0.0, 2.0), b)
            else:
                edge_cost = t_loaded(edge, L[eid], b)

            ng = g[u] + edge_cost
            if ng < g.get(v, 1e18):
                g[v] = ng
                prev[v] = (u, eid)
                heapq.heappush(pq, (ng + h(v), v))

    if dst not in prev:
        raise HTTPException(422, f"No route between {src} and {dst}")

    path, eids, n = [dst], [], dst
    while n != src:
        n, eid = prev[n][0], prev[n][1]
        eids.append(eid)
        path.append(n)
    return path[::-1], eids[::-1], expanded

def summarize(path: List[int], eids: List[int], L: Dict[int, float], expanded: Optional[int] = None, b: float = 0.0) -> Dict[str, Any]:
    mins = [t_loaded(EDGES[i], L[i], b) for i in eids]
    return dict(
        path=path,
        coords=[NODES[n] for n in path],
        minutes=round(sum(mins), 2),
        km=round(sum(EDGES[i]["km"] for i in eids), 2),
        expanded=expanded,
        cumulative=[round(sum(mins[:k]), 2) for k in range(len(mins) + 1)]
    )

# ---------- 5. Database (SQLite) & Authentication ----------
import sqlite3

DB = os.environ.get("TRAFFIC_DB", "traffic.db")

def init_db_conn(c):
    c.executescript("""
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
 role TEXT NOT NULL CHECK(role IN ('user','bus_operator','ambulance','admin')),
 status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','suspended')), amb_code TEXT UNIQUE, created_at TEXT);
CREATE TABLE IF NOT EXISTS trips(id INTEGER PRIMARY KEY, operator_id INTEGER NOT NULL REFERENCES users(id), hospital_id INTEGER, src INTEGER, dst INTEGER,
 status TEXT CHECK(status IN ('Ready','Active','Completed','Cancelled')), est_minutes REAL, km REAL, started_at TEXT, completed_at TEXT);
CREATE TABLE IF NOT EXISTS scenarios(id INTEGER PRIMARY KEY, created_by INTEGER REFERENCES users(id), name TEXT, config TEXT, result TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS traffic_observations(id INTEGER PRIMARY KEY, road_id INTEGER, observed_at TEXT, speed_kmh REAL, free_speed_kmh REAL, load REAL, data_source TEXT);
CREATE TABLE IF NOT EXISTS bus_routes(id INTEGER PRIMARY KEY, name TEXT UNIQUE, operator_id INTEGER REFERENCES users(id), nodes TEXT, status TEXT DEFAULT 'active');
CREATE TABLE IF NOT EXISTS bus_stops(id INTEGER PRIMARY KEY, name TEXT NOT NULL, node INTEGER NOT NULL, UNIQUE(name, node));
CREATE TABLE IF NOT EXISTS bus_route_stops(route_id INTEGER REFERENCES bus_routes(id), stop_id INTEGER REFERENCES bus_stops(id), seq INTEGER, PRIMARY KEY(route_id, seq));
CREATE TABLE IF NOT EXISTS bus_schedules(route_id INTEGER PRIMARY KEY REFERENCES bus_routes(id), first TEXT, last TEXT, headway REAL, fleet INTEGER);
CREATE TABLE IF NOT EXISTS proposals(id INTEGER PRIMARY KEY, route_id INTEGER REFERENCES bus_routes(id), operator_id INTEGER REFERENCES users(id), nodes TEXT, note TEXT, preview TEXT,
 status TEXT DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected')), created_at TEXT);
CREATE TABLE IF NOT EXISTS location_updates(id INTEGER PRIMARY KEY, trip_id INTEGER REFERENCES trips(id), lat REAL, lon REAL, recorded_at TEXT);
CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, user_id INTEGER, action TEXT, at TEXT);
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id INTEGER REFERENCES users(id), expires_at REAL, created_at TEXT);
CREATE TABLE IF NOT EXISTS model_versions(id INTEGER PRIMARY KEY, version_tag TEXT UNIQUE, model_type TEXT, trained_at TEXT, n_train INTEGER, n_test INTEGER, metrics TEXT, is_active INTEGER);
""")
    pcols = [r[1] for r in c.execute("PRAGMA table_info(proposals)")]
    if "kind" not in pcols: c.execute("ALTER TABLE proposals ADD COLUMN kind TEXT DEFAULT 'route'")
    if "schedule" not in pcols: c.execute("ALTER TABLE proposals ADD COLUMN schedule TEXT")
    ucols = [r[1] for r in c.execute("PRAGMA table_info(users)")]
    for col in ("requested_role", "request_status", "request_note"):
        if col not in ucols: c.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT")
    if "severity" not in [r[1] for r in c.execute("PRAGMA table_info(trips)")]:
        c.execute("ALTER TABLE trips ADD COLUMN severity TEXT DEFAULT 'routine'")
    if not c.execute("SELECT 1 FROM users WHERE role='admin'").fetchone():
        em, pw = os.environ.get("ADMIN_EMAIL", "admin@example.com"), os.environ.get("ADMIN_PASSWORD") or secrets.token_urlsafe(9)
        c.execute("INSERT INTO users(name,email,password_hash,role,created_at) VALUES('Admin',?,?,'admin',?)", (em.lower(), hash_pw(pw), now()))
        print(f"[setup] admin created: {em} / {pw}")
    if "BUS" in globals() and not c.execute("SELECT 1 FROM bus_routes").fetchone():
        for n, nodes in BUS.items():
            c.execute("INSERT OR IGNORE INTO bus_routes(name,nodes) VALUES(?,?)", (n, json.dumps(nodes)))
    c.commit()

def db():
    path = os.environ.get("TRAFFIC_DB", DB)
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    # Verify tables exist, else auto-init
    if not c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'").fetchone():
        init_db_conn(c)
    return c

def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

def hash_pw(p: str, salt: bytes = None) -> str:
    salt = salt or os.urandom(16)
    return salt.hex() + "$" + hashlib.pbkdf2_hmac("sha256", p.encode(), salt, 200_000).hex()

def check_pw(p: str, h: str) -> bool:
    try:
        s = h.split("$")[0]
        return secrets.compare_digest(hash_pw(p, bytes.fromhex(s)), h)
    except Exception:
        return False

def audit(c, uid: Optional[int], action: str):
    c.execute("INSERT INTO audit(user_id,action,at) VALUES(?,?,?)", (uid, action, now()))

def init_db():
    with db() as c:
        init_db_conn(c)

init_db()

TOKENS: Dict[str, Tuple[int, float]] = {}
FAILS: Dict[str, Tuple[int, float]] = {}

class Reg(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=120)
    password: str = Field(min_length=8, max_length=100)
    request_role: Optional[str] = Field(None, pattern="^(bus_operator|ambulance)$")
    request_note: str = Field("", max_length=200)

class Login(BaseModel):
    email: str
    password: str

@app.post("/api/register", status_code=201)
def register(b: Reg):
    try:
        with db() as c:
            c.execute(
                "INSERT INTO users(name,email,password_hash,role,created_at,requested_role,request_status,request_note) VALUES(?,?,?,'user',?,?,?,?)",
                (b.name, b.email.lower(), hash_pw(b.password), now(), b.request_role, "pending" if b.request_role else None, b.request_note)
            )
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Email already registered")
    return dict(ok=True)

@app.post("/api/login")
def login(b: Login):
    em = b.email.lower()
    n, until = FAILS.get(em, (0, 0))
    if until > time.time():
        raise HTTPException(429, "Too many attempts, try again in a minute")
    with db() as c:
        u = c.execute("SELECT * FROM users WHERE email=?", (em,)).fetchone()
    if not u or not check_pw(b.password, u["password_hash"]):
        FAILS[em] = (n + 1, time.time() + 60 if n + 1 >= 5 else 0)
        raise HTTPException(401, "Invalid credentials")
    if u["status"] != "active":
        raise HTTPException(403, "Account suspended")
    FAILS.pop(em, None)
    t = secrets.token_hex(24)
    exp = time.time() + 8 * 3600
    TOKENS[t] = (u["id"], exp)
    try:
        with db() as c:
            c.execute("INSERT OR REPLACE INTO sessions(token, user_id, expires_at, created_at) VALUES(?,?,?,?)", (t, u["id"], exp, now()))
    except Exception:
        pass
    return dict(token=t, role=u["role"], name=u["name"], request_status=u["request_status"])

def need(*roles, strict=False):
    def dep(x_token: str = Header("")):
        s = TOKENS.get(x_token)
        if not s or s[1] < time.time():
            # Check persistent sessions in db
            with db() as c:
                row = c.execute("SELECT user_id, expires_at FROM sessions WHERE token=? AND expires_at > ?", (x_token, time.time())).fetchone()
                if row:
                    s = (row["user_id"], row["expires_at"])
                    TOKENS[x_token] = s
                else:
                    raise HTTPException(401, "Login required")
        with db() as c:
            u = c.execute("SELECT * FROM users WHERE id=?", (s[0],)).fetchone()
        if not u or u["status"] != "active":
            raise HTTPException(401, "Account not active")
        if roles and u["role"] not in roles and not (u["role"] == "admin" and not strict):
            raise HTTPException(403, f"Role '{u['role']}' not allowed")
        return dict(u)
    return dep

@app.post("/api/logout")
def logout(x_token: str = Header("")):
    TOKENS.pop(x_token, None)
    try:
        with db() as c:
            c.execute("DELETE FROM sessions WHERE token=?", (x_token,))
    except Exception:
        pass
    return dict(ok=True)

@app.get("/api/me")
def me(u=Depends(need())):
    return {k: u[k] for k in ("id", "name", "email", "role", "amb_code", "requested_role", "request_status")}

class Prof(BaseModel):
    name: str = Field(min_length=1, max_length=60)

@app.patch("/api/me")
def edit_me(b: Prof, u=Depends(need())):
    with db() as c:
        c.execute("UPDATE users SET name=? WHERE id=?", (b.name, u["id"]))
    return dict(ok=True)

# ---------- 6. Network API ----------
@app.get("/api/network")
def api_network(_=Depends(need())):
    L = loads()
    return dict(
        nodes={n: c for n, c in NODES.items()},
        status=traffic_status(),
        bounds=[[BBOX[0], BBOX[1]], [BBOX[2], BBOX[3]]],
        edges=[
            dict(
                id=i, a=e["a"], b=e["b"], km=e["km"], speed=e["speed"],
                load=round(L[i], 2), congested=i in OVERRIDES, live=i in LIVE["loads"] and source() == "live"
            )
            for i, e in EDGES.items()
        ]
    )

@app.get("/api/status")
def api_status(_=Depends(need())):
    return traffic_status()

@app.post("/api/admin/refresh-live")
def force_live(_=Depends(need("admin", strict=True))):
    if source() != "live":
        raise HTTPException(409, "Set TRAFFIC_SOURCE=live and TOMTOM_API_KEY, then restart")
    refresh_live()
    return traffic_status()

class Cong(BaseModel):
    edge_id: int
    congested: bool = True

@app.post("/api/congestion")
def congestion(b: Cong, _=Depends(need("admin"))):
    (OVERRIDES.add if b.congested else OVERRIDES.discard)(b.edge_id)
    return dict(congested=sorted(OVERRIDES))

@app.post("/api/reset")
def reset(_=Depends(need("admin"))):
    OVERRIDES.clear()
    return dict(ok=True)

@app.get("/api/route")
def api_route(
    src: int, dst: int, algo: str = "astar", mode: str = "aware",
    departure_hour: Optional[float] = None, dow: int = 1, _=Depends(need())
):
    if algo not in ("astar", "dijkstra") or mode not in ("aware", "static"):
        raise HTTPException(422, "Bad algo/mode")
    chk(src); chk(dst)
    L = loads()
    p, e, x = search(src, dst, algo, mode, L, departure_hour=departure_hour, dow=dow)
    return summarize(p, e, L, x)

@app.get("/api/compare")
def compare(src: int, dst: int, departure_hour: Optional[float] = None, dow: int = 1, _=Depends(need())):
    chk(src); chk(dst)
    L = loads()
    out = {}
    for name, mode in (("static_shortest", "static"), ("traffic_aware", "aware")):
        p, e, x = search(src, dst, "astar", mode, L)
        out[name] = summarize(p, e, L, x)
    if departure_hour is not None:
        p_pred, e_pred, x_pred = search(src, dst, "astar", "aware", L, departure_hour=departure_hour, dow=dow)
        out["predicted_traffic"] = summarize(p_pred, e_pred, L, x_pred)
    s, a = out["static_shortest"]["minutes"], out["traffic_aware"]["minutes"]
    out["saved_minutes"] = round(s - a, 2)
    out["saved_pct"] = round(100.0 * (s - a) / s, 1) if s else 0.0
    p1, _, x1 = search(src, dst, "dijkstra", "aware", L)
    out["nodes_expanded"] = dict(dijkstra=x1, astar=out["traffic_aware"]["expanded"])
    return out

@app.get("/api/predict")
def predict(hour: int = Query(ge=0, le=23), dow: int = Query(ge=0, le=6), _=Depends(need())):
    pred = rf.predict([feats(e, hour, dow) for e in EDGES.values()])
    top = sorted(zip(EDGES, pred), key=lambda t: -t[1])[:5]
    return dict(
        hour=hour, dow=dow, mean_load=round(float(pred.mean()), 3),
        hotspots=[dict(edge=i, load=round(float(v), 2)) for i, v in top]
    )

@app.get("/api/predict/curve")
def curve(dow: int = Query(ge=0, le=6), _=Depends(need())):
    X_curve = [feats(e, h, dow) for h in range(24) for e in EDGES.values()]
    p = rf.predict(X_curve).reshape(24, -1).mean(1)
    bl = [float(np.mean([base.get((i, h), glob_base) for i in EDGES])) for h in range(24)]
    return dict(
        dow=dow, hours=list(range(24)),
        random_forest=[round(float(x), 3) for x in p],
        baseline_hourly_mean=[round(x, 3) for x in bl],
        data_source="Model trained on SYNTHETIC data"
    )

@app.get("/api/metrics")
def metrics(_=Depends(need())):
    return {**METRICS, "live_retrained": LIVE_MODEL["metrics"]}

def _auto_bus():
    L0 = {i: 0.0 for i in EDGES}
    o = min(NODES, key=lambda n: sum(NODES[n]))
    d = max(NODES, key=lambda n: hav(o, n))
    p1, e1, _x = search(o, d, "astar", "static", L0)
    p2, _e, _y = search(o, d, "astar", "aware", {i: (1.5 if i in e1 else 0.0) for i in EDGES})
    return {"Corridor A (shortest)": p1, "Corridor B (alternative)": p2}

BUS = _auto_bus() if GRAPH != "simulated-grid" else {"Route A (direct)": [12, 13, 14, 15, 16, 17], "Route B (detour via row 3)": [12, 18, 19, 20, 21, 22, 23, 17]}

def seed_bus():
    with db() as c:
        if not c.execute("SELECT 1 FROM bus_routes").fetchone():
            for n, nodes in BUS.items():
                c.execute("INSERT INTO bus_routes(name,nodes) VALUES(?,?)", (n, json.dumps(nodes)))

seed_bus()

def route_eids(nodes: List[int]) -> List[int]:
    out = []
    for a, b in zip(nodes, nodes[1:]):
        m = next((i for v, i in ADJ.get(a, []) if v == b), None)
        if m is None:
            raise HTTPException(422, f"Junctions {a} and {b} are not connected by a road")
        out.append(m)
    return out

def stops_of(c, rid: int):
    return c.execute("SELECT s.name,s.node FROM bus_route_stops rs JOIN bus_stops s ON s.id=rs.stop_id WHERE rs.route_id=? ORDER BY rs.seq", (rid,)).fetchall()

def my_routes(u):
    with db() as c:
        q = "SELECT * FROM bus_routes" + ("" if u["role"] == "admin" else " WHERE operator_id=?")
        return [
            {**dict(r), "nodes": json.loads(r["nodes"]), "stops": [f"{x['name']}:{x['node']}" for x in stops_of(c, r["id"])]}
            for r in c.execute(q, () if u["role"] == "admin" else (u["id"],))
        ]

def analyse(nodes: List[int], L: Dict[int, float]):
    eids = route_eids(nodes)
    s = summarize(nodes, eids, L)
    return {**s, "avg_edge_load": round(float(np.mean([L[i] for i in eids])), 2), "congested_segments": [i for i in eids if L[i] >= 1.0]}

@app.get("/api/bus/routes")
def bus_routes(u=Depends(need("bus_operator"))):
    return my_routes(u)

@app.get("/api/bus/compare")
def bus_compare(u=Depends(need("bus_operator"))):
    L = loads()
    return {r["name"]: analyse(r["nodes"], L) for r in my_routes(u)}

class Prop(BaseModel):
    route_id: int
    nodes: List[int] = Field(min_length=2, max_length=80)
    note: str = Field("", max_length=300)

@app.post("/api/bus/proposals", status_code=201)
def propose(b: Prop, u=Depends(need("bus_operator", strict=True))):
    cur = next((r for r in my_routes(u) if r["id"] == b.route_id), None)
    if not cur:
        raise HTTPException(403, "Route is not assigned to you")
    L = loads()
    a, p = analyse(cur["nodes"], L), analyse(b.nodes, L)
    pv = {k: {x: v[x] for x in ("minutes", "km", "avg_edge_load")} for k, v in (("current", a), ("proposed", p))}
    with db() as c:
        pid = c.execute(
            "INSERT INTO proposals(route_id,operator_id,nodes,note,preview,created_at) VALUES(?,?,?,?,?,?)",
            (b.route_id, u["id"], json.dumps(b.nodes), b.note, json.dumps(pv), now())
        ).lastrowid
    return dict(id=pid, current_minutes=a["minutes"], proposed_minutes=p["minutes"])

def summ(kind: str, pv: Dict[str, Any]) -> str:
    a, b = pv["current"], pv["proposed"]
    return f"{a['minutes']} to {b['minutes']} min" if kind != "schedule" else f"headway {a['headway']} to {b['headway']} min, fleet {a['fleet']} to {b['fleet']}, buses needed {a['needed']} to {b['needed']}"

@app.get("/api/bus/proposals")
def api_proposals(u=Depends(need("bus_operator"))):
    with db() as c:
        q = "SELECT p.id,p.route_id,r.name route,p.kind,p.note,p.preview,p.status,p.created_at FROM proposals p JOIN bus_routes r ON r.id=p.route_id" + ("" if u["role"] == "admin" else " WHERE p.operator_id=?") + " ORDER BY p.id DESC"
        return [
            {**dict(r), "preview": json.loads(r["preview"]), "summary": summ(r["kind"], json.loads(r["preview"]))}
            for r in c.execute(q, () if u["role"] == "admin" else (u["id"],))
        ]

class Dec(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")

@app.post("/api/admin/proposals/{pid}/decision")
def decide(pid: int, b: Dec, a=Depends(need("admin", strict=True))):
    with db() as c:
        p = c.execute("SELECT * FROM proposals WHERE id=? AND status='pending'", (pid,)).fetchone()
        if not p:
            raise HTTPException(404, "No pending proposal")
        c.execute("UPDATE proposals SET status=? WHERE id=?", (b.decision, pid))
        if b.decision == "approved":
            if p["kind"] == "schedule":
                x = json.loads(p["schedule"])
                c.execute(
                    "INSERT OR REPLACE INTO bus_schedules(route_id,first,last,headway,fleet) VALUES(?,?,?,?,?)",
                    (p["route_id"], x["first"], x["last"], x["headway_min"], x["fleet"])
                )
            else:
                c.execute("UPDATE bus_routes SET nodes=? WHERE id=?", (p["nodes"], p["route_id"]))
        audit(c, a["id"], f"{b.decision} bus proposal {pid}")
    return dict(ok=True)

class Assign(BaseModel):
    operator_id: int

@app.post("/api/admin/bus-routes/{rid}/assign")
def assign(rid: int, b: Assign, a=Depends(need("admin", strict=True))):
    with db() as c:
        o = c.execute("SELECT role FROM users WHERE id=?", (b.operator_id,)).fetchone()
        if not o or o["role"] != "bus_operator":
            raise HTTPException(422, "operator_id must be a bus operator account")
        if c.execute("UPDATE bus_routes SET operator_id=? WHERE id=?", (b.operator_id, rid)).rowcount == 0:
            raise HTTPException(404, "No such route")
        audit(c, a["id"], f"assigned bus route {rid} to user {b.operator_id}")
    return dict(ok=True)

# ---------- 7b. Bus Stops & Timetables ----------
DWELL, LAYOVER = float(os.environ.get("BUS_DWELL_MIN", "0.5")), 5.0
DEFAULT_SCHED = dict(first="06:00", last="22:00", headway_min=15.0, fleet=4)
HHMM = r"^([01]\d|2[0-3]):[0-5]\d$"

def hm(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)

def fmt(m: float) -> str:
    return f"{int(m) // 60 % 24:02d}:{int(m) % 60:02d}"

def get_sched(rid: int):
    with db() as c:
        r = c.execute("SELECT * FROM bus_schedules WHERE route_id=?", (rid,)).fetchone()
    return ({"first": r["first"], "last": r["last"], "headway_min": r["headway"], "fleet": r["fleet"]}, False) if r else (DEFAULT_SCHED, True)

def owned(u, rid: int):
    r = next((x for x in my_routes(u) if x["id"] == rid), None)
    if not r:
        raise HTTPException(404, "No such route for you")
    return r

def stop_analysis(r, L: Dict[int, float], sc: Dict[str, Any]):
    n = r["nodes"]
    eids = route_eids(n)
    idx = {}
    for k, v in enumerate(n):
        idx.setdefault(v, k)
    now_, free_ = [0.0], [0.0]
    for i in eids:
        now_.append(now_[-1] + t_loaded(EDGES[i], L[i]))
        free_.append(free_[-1] + t_free(EDGES[i]))
    with db() as c:
        st = [(x["name"], x["node"]) for x in stops_of(c, r["id"]) if x["node"] in idx] or [("Start", n[0]), ("End", n[-1])]
    rows = [
        dict(
            stop=nm,
            node=nd,
            free_flow=round(free_[idx[nd]] + k * DWELL, 1),
            expected=round(now_[idx[nd]] + k * DWELL, 1)
        )
        for k, (nm, nd) in enumerate(st)
    ]
    for x in rows:
        x["delay"] = round(x["expected"] - x["free_flow"], 1)

    def m(trip):
        cyc = 2.0 * trip + LAYOVER
        need_fleet = math.ceil(cyc / sc["headway_min"])
        return dict(cycle_minutes=round(cyc, 1), needed=need_fleet, short_by=max(0, need_fleet - sc["fleet"]))

    a = m(rows[-1]["expected"])
    return dict(
        stops=rows,
        trip_minutes=rows[-1]["expected"],
        **a,
        fleet=sc["fleet"],
        headway=sc["headway_min"],
        needed_free_flow=m(rows[-1]["free_flow"])["needed"],
        trips_per_day=int((hm(sc["last"]) - hm(sc["first"])) // sc["headway_min"]) + 1,
        congested_segments=[i for i in eids if L[i] >= 1.0]
    )

@app.get("/api/bus/routes/{rid}/analysis")
def api_bus_analysis(rid: int, u=Depends(need("bus_operator"))):
    r = owned(u, rid)
    sc, dflt = get_sched(rid)
    a = stop_analysis(r, loads(), sc)
    a["timetable"] = [
        dict(
            depart=fmt(hm(sc["first"]) + k * sc["headway_min"]),
            arrive_last_stop=fmt(hm(sc["first"]) + k * sc["headway_min"] + a["trip_minutes"])
        )
        for k in range(6)
    ]
    a.update(
        schedule=sc,
        schedule_is_default=dflt,
        data_source=traffic_status()["label"],
        assumptions=f"Dwell {DWELL} min per stop, {LAYOVER} min layover, return trip assumed equal to outbound"
    )
    return a

class StopIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    node: int

class Stops(BaseModel):
    stops: List[StopIn] = Field(min_length=2, max_length=60)

@app.post("/api/bus/routes/{rid}/stops")
def set_stops(rid: int, b: Stops, u=Depends(need("bus_operator"))):
    r = owned(u, rid)
    pos = -1
    for x in b.stops:
        if x.node not in r["nodes"][pos + 1:]:
            raise HTTPException(422, f"Stop at junction {x.node} is not on the route, in order")
        pos = r["nodes"].index(x.node, pos + 1)
    with db() as c:
        c.execute("DELETE FROM bus_route_stops WHERE route_id=?", (rid,))
        for k, x in enumerate(b.stops):
            c.execute("INSERT OR IGNORE INTO bus_stops(name,node) VALUES(?,?)", (x.name, x.node))
            sid = c.execute("SELECT id FROM bus_stops WHERE name=? AND node=?", (x.name, x.node)).fetchone()[0]
            c.execute("INSERT INTO bus_route_stops(route_id,stop_id,seq) VALUES(?,?,?)", (rid, sid, k))
        audit(c, u["id"], f"set stops of bus route {rid}")
    return dict(ok=True)

class Sched(BaseModel):
    first: str = Field(pattern=HHMM)
    last: str = Field(pattern=HHMM)
    headway_min: float = Field(ge=2, le=120)
    fleet: int = Field(ge=1, le=200)

def check_sched(b: Sched):
    if hm(b.last) <= hm(b.first):
        raise HTTPException(422, "Last departure must be after the first")

@app.post("/api/admin/bus-routes/{rid}/schedule")
def admin_sched(rid: int, b: Sched, a=Depends(need("admin", strict=True))):
    check_sched(b)
    with db() as c:
        if not c.execute("SELECT 1 FROM bus_routes WHERE id=?", (rid,)).fetchone():
            raise HTTPException(404, "No such route")
        c.execute(
            "INSERT OR REPLACE INTO bus_schedules(route_id,first,last,headway,fleet) VALUES(?,?,?,?,?)",
            (rid, b.first, b.last, b.headway_min, b.fleet)
        )
        audit(c, a["id"], f"set schedule of bus route {rid}")
    return dict(ok=True)

class SchedProp(Sched):
    route_id: int
    note: str = Field("", max_length=300)

@app.post("/api/bus/schedule-proposals", status_code=201)
def propose_sched(b: SchedProp, u=Depends(need("bus_operator", strict=True))):
    r = next((x for x in my_routes(u) if x["id"] == b.route_id), None)
    if not r:
        raise HTTPException(403, "Route is not assigned to you")
    check_sched(b)
    L = loads()
    cur, _d = get_sched(r["id"])
    new = b.model_dump(include={"first", "last", "headway_min", "fleet"})
    a = stop_analysis(r, L, cur)
    p = stop_analysis(r, L, new)
    pv = dict(
        current=dict(headway=cur["headway_min"], fleet=cur["fleet"], needed=a["needed"]),
        proposed=dict(headway=b.headway_min, fleet=b.fleet, needed=p["needed"])
    )
    with db() as c:
        pid = c.execute(
            "INSERT INTO proposals(route_id,operator_id,nodes,note,preview,created_at,kind,schedule) VALUES(?,?,?,?,?,?,'schedule',?)",
            (r["id"], u["id"], json.dumps(r["nodes"]), b.note, json.dumps(pv), now(), json.dumps(new))
        ).lastrowid
    return dict(id=pid, headway=b.headway_min, fleet=b.fleet, needed=p["needed"], short_by=p["short_by"])

# ---------- 8. Emergency Trips & Hospitals ----------
HOSP = HOSP_FILE or {1: ("City Hospital", 35), 2: ("Central Hospital", 14), 3: ("North General", 5)}

def chk(n: int) -> int:
    if n not in NODES:
        raise HTTPException(422, f"Unknown junction {n}")
    return n

def nearest(lat: float, lon: float) -> int:
    if not (BBOX[0] - .02 <= lat <= BBOX[2] + .02 and BBOX[1] - .02 <= lon <= BBOX[3] + .02):
        raise HTTPException(422, "Location outside simulated area; use simulated start")
    return min(NODES, key=lambda n: (NODES[n][0] - lat) ** 2 + (NODES[n][1] - lon) ** 2)

@app.get("/api/hospitals")
def api_hospitals(_=Depends(need())):
    return [dict(id=k, name=v[0], node=v[1]) for k, v in HOSP.items()]

class Start(BaseModel):
    severity: str = Field("routine", pattern="^(critical|urgent|routine)$")
    hospital_id: int
    src: Optional[int] = None
    lat: Optional[float] = None
    lon: Optional[float] = None

@app.post("/api/emergency/start")
def emergency_start(b: Start, u=Depends(need("ambulance", strict=True))):
    if b.hospital_id not in HOSP:
        raise HTTPException(422, "Unknown hospital")
    src = nearest(b.lat, b.lon) if b.lat is not None and b.lon is not None else chk(b.src if b.src is not None else 0)
    dst = HOSP[b.hospital_id][1]
    if src == dst:
        raise HTTPException(422, "Already at destination")
    with db() as c:
        if c.execute("SELECT 1 FROM trips WHERE operator_id=? AND status='Active'", (u["id"],)).fetchone():
            raise HTTPException(409, "A trip is already active")
        L = loads()
        bp = BYPASS[b.severity]
        p, e, x = search(src, dst, "astar", "aware", L, bp)
        rec = summarize(p, e, L, x, bp)
        ps, es, _ = search(src, dst, "astar", "static", L)
        cur = c.execute(
            "INSERT INTO trips(operator_id,hospital_id,src,dst,status,est_minutes,km,started_at,severity) VALUES(?,?,?,?,'Active',?,?,?,?)",
            (u["id"], b.hospital_id, src, dst, rec["minutes"], rec["km"], now(), b.severity)
        )
        tid = cur.lastrowid
    return dict(
        trip_id=tid,
        status="Active",
        recommended=rec,
        distance_only=summarize(ps, es, L, None, bp),
        severity=b.severity,
        note="Simulated data. Severity sets a queue-bypass ASSUMPTION; recommendation only, no signal control."
    )

class Fin(BaseModel):
    status: str = Field(pattern="^(Completed|Cancelled)$")

@app.post("/api/emergency/{tid}/finish")
def emergency_finish(tid: int, b: Fin, u=Depends(need("ambulance", strict=True))):
    with db() as c:
        if c.execute(
            "UPDATE trips SET status=?,completed_at=? WHERE id=? AND operator_id=? AND status='Active'",
            (b.status, now(), tid, u["id"])
        ).rowcount == 0:
            raise HTTPException(404, "No such active trip")
    return dict(ok=True)

@app.get("/api/emergency/trips")
def emergency_trips(u=Depends(need("ambulance"))):
    with db() as c:
        q = "SELECT t.*,u.amb_code,(SELECT COUNT(*) FROM location_updates l WHERE l.trip_id=t.id) positions FROM trips t JOIN users u ON u.id=t.operator_id" + ("" if u["role"] == "admin" else " WHERE t.operator_id=?") + " ORDER BY t.id DESC"
        return [dict(r) for r in c.execute(q, () if u["role"] == "admin" else (u["id"],))]

class Loc(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)

@app.post("/api/emergency/{tid}/location")
def emergency_location(tid: int, b: Loc, u=Depends(need("ambulance", strict=True))):
    with db() as c:
        if not c.execute("SELECT 1 FROM trips WHERE id=? AND operator_id=? AND status='Active'", (tid, u["id"])).fetchone():
            raise HTTPException(404, "No such active trip")
        c.execute("INSERT INTO location_updates(trip_id,lat,lon,recorded_at) VALUES(?,?,?,?)", (tid, b.lat, b.lon, now()))
    return dict(ok=True)

@app.get("/api/emergency/{tid}/track")
def emergency_track(tid: int, u=Depends(need("ambulance"))):
    with db() as c:
        t = c.execute("SELECT operator_id FROM trips WHERE id=?", (tid,)).fetchone()
        if not t or (u["role"] != "admin" and t["operator_id"] != u["id"]):
            raise HTTPException(404, "No such trip")
        return [dict(r) for r in c.execute("SELECT lat,lon,recorded_at FROM location_updates WHERE trip_id=? ORDER BY id", (tid,))]

# ---------- 9. Admin User Management & Audit Log ----------
class NewUser(Reg):
    role: str = Field(pattern="^(bus_operator|ambulance)$")
    amb_code: Optional[str] = Field(None, max_length=20)

@app.post("/api/admin/users", status_code=201)
def create_user(b: NewUser, a=Depends(need("admin", strict=True))):
    if b.role == "ambulance" and not b.amb_code:
        raise HTTPException(422, "amb_code required for ambulance operators")
    try:
        with db() as c:
            c.execute(
                "INSERT INTO users(name,email,password_hash,role,amb_code,created_at) VALUES(?,?,?,?,?,?)",
                (b.name, b.email.lower(), hash_pw(b.password), b.role, b.amb_code, now())
            )
            audit(c, a["id"], f"created {b.role} account {b.email}")
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Email or ambulance code already exists")
    return dict(ok=True)

@app.get("/api/admin/users")
def list_users(_=Depends(need("admin", strict=True))):
    with db() as c:
        return [dict(r) for r in c.execute("SELECT id,name,email,role,status,amb_code,created_at FROM users")]

class Stat(BaseModel):
    status: str = Field(pattern="^(active|suspended)$")

@app.post("/api/admin/users/{uid}/status")
def set_status(uid: int, b: Stat, a=Depends(need("admin", strict=True))):
    if uid == a["id"]:
        raise HTTPException(422, "Cannot change your own status")
    with db() as c:
        if c.execute("UPDATE users SET status=? WHERE id=?", (b.status, uid)).rowcount == 0:
            raise HTTPException(404, "No such user")
        audit(c, a["id"], f"set user {uid} {b.status}")
    for t, (i, _e) in list(TOKENS.items()):
        if i == uid and b.status == "suspended":
            TOKENS.pop(t, None)
    return dict(ok=True)

@app.get("/api/admin/audit")
def audit_log(_=Depends(need("admin", strict=True))):
    with db() as c:
        return [dict(r) for r in c.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 50")]

@app.get("/api/admin/requests")
def role_requests(_=Depends(need("admin", strict=True))):
    with db() as c:
        return [dict(r) for r in c.execute("SELECT id,name,email,requested_role,request_note,created_at FROM users WHERE role='user' AND request_status='pending'")]

class ReqDec(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    amb_code: Optional[str] = Field(None, max_length=20)

@app.post("/api/admin/requests/{uid}/decision")
def role_decide(uid: int, b: ReqDec, a=Depends(need("admin", strict=True))):
    with db() as c:
        u = c.execute("SELECT * FROM users WHERE id=? AND role='user' AND request_status='pending'", (uid,)).fetchone()
        if not u:
            raise HTTPException(404, "No pending request")
        if b.decision == "approve":
            amb = u["requested_role"] == "ambulance"
            if amb and not b.amb_code:
                raise HTTPException(422, "amb_code required to approve an ambulance operator")
            try:
                c.execute(
                    "UPDATE users SET role=?,amb_code=?,requested_role=NULL,request_status=NULL WHERE id=?",
                    (u["requested_role"], b.amb_code if amb else None, uid)
                )
            except sqlite3.IntegrityError:
                raise HTTPException(409, "Ambulance code already in use")
        else:
            c.execute("UPDATE users SET request_status='rejected' WHERE id=?", (uid,))
        audit(c, a["id"], f"{b.decision}d role request of user {uid} ({u['requested_role']})".replace("rejectd", "rejected"))
    return dict(ok=True)

# ---------- 10. Scenarios & Incident Simulation ----------
class Scn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    src: int
    dst: int
    edge_ids: List[int] = Field(min_length=1, max_length=20)
    level: float = Field(ge=0, le=2)

@app.post("/api/scenario")
def scenario(b: Scn, u=Depends(need("admin", strict=True))):
    chk(b.src); chk(b.dst)
    if any(i not in EDGES for i in b.edge_ids):
        raise HTTPException(422, "Unknown road id")
    L0 = loads()
    L1 = {**L0, **{i: b.level for i in b.edge_ids}}
    p0, e0, _a = search(b.src, b.dst, "astar", "aware", L0)
    base_res = summarize(p0, e0, L0)
    stay_res = summarize(p0, e0, L1)
    p1, e1, _b = search(b.src, b.dst, "astar", "aware", L1)
    new_res = summarize(p1, e1, L1)
    res = dict(
        baseline=base_res,
        same_route_after_change=stay_res,
        rerouted=new_res,
        delay_if_no_reroute=round(stay_res["minutes"] - base_res["minutes"], 2),
        recovered_by_rerouting=round(stay_res["minutes"] - new_res["minutes"], 2),
        data_source="SIMULATED"
    )
    with db() as c:
        c.execute(
            "INSERT INTO scenarios(created_by,name,config,result,created_at) VALUES(?,?,?,?,?)",
            (u["id"], b.name, b.model_dump_json(), json.dumps(res), now())
        )
        audit(c, u["id"], f"ran scenario {b.name}")
    return res

@app.get("/api/scenarios")
def scenarios(_=Depends(need("admin", strict=True))):
    with db() as c:
        return [
            dict(id=r["id"], name=r["name"], created_at=r["created_at"], result=json.loads(r["result"]))
            for r in c.execute("SELECT * FROM scenarios ORDER BY id DESC LIMIT 20")
        ]

@app.get("/api/reports")
def reports(_=Depends(need("admin", strict=True))):
    with db() as c:
        trips_list = [dict(r) for r in c.execute("SELECT severity,status,COUNT(*) n,ROUND(AVG(est_minutes),2) avg_min FROM trips GROUP BY severity,status")]
        scs = [json.loads(r[0]) for r in c.execute("SELECT result FROM scenarios")]
        props = {r[0]: r[1] for r in c.execute("SELECT status,COUNT(*) FROM proposals GROUP BY status")}
        obs = c.execute("SELECT COUNT(*) FROM traffic_observations").fetchone()[0]
    m_calc = lambda k: round(float(np.mean([x[k] for x in scs])), 2) if scs else None
    return dict(
        trips=trips_list,
        scenarios=dict(
            count=len(scs),
            mean_delay_if_no_reroute=m_calc("delay_if_no_reroute"),
            mean_recovered=m_calc("recovered_by_rerouting")
        ),
        proposals=props,
        prediction=METRICS,
        live_observations=obs,
        traffic=traffic_status()
    )

# ---------- 11. Place Search (OSM Nominatim) ----------
GEO_CACHE: Dict[str, Any] = {}
GEO_LAST: List[float] = [0.0]

def geocode_remote(q: str):
    wait = GEO_LAST[0] + 1.1 - time.time()
    if wait > 0:
        time.sleep(wait)
    GEO_LAST[0] = time.time()
    qs = urllib.parse.urlencode({
        "q": q,
        "format": "jsonv2",
        "limit": 5,
        "bounded": 1,
        "viewbox": f"{BBOX[1]},{BBOX[2]},{BBOX[3]},{BBOX[0]}"
    })
    req = urllib.request.Request(
        "https://nominatim.openstreetmap.org/search?" + qs,
        headers={"User-Agent": os.environ.get("GEOCODER_UA", "team10-traffic-capstone (set GEOCODER_UA with your contact)")}
    )
    with urllib.request.urlopen(req, timeout=8) as r:
        return json.load(r)

@app.get("/api/places/search")
def places(q: str = Query(min_length=2, max_length=80), _=Depends(need())):
    ql = q.strip().lower()
    out = []
    err = None

    def add(name: str, node: int, src: str):
        out.append(dict(name=name, node=node, lat=NODES[node][0], lon=NODES[node][1], source=src))

    for nm, nd in HOSP.values():
        if ql in nm.lower():
            add(nm, nd, "hospital")

    with db() as c:
        for r in c.execute("SELECT name,node FROM bus_stops WHERE lower(name) LIKE ? LIMIT 8", (f"%{ql}%",)):
            if r["node"] in NODES:
                add(r["name"], r["node"], "bus stop")

    if ql.isdigit() and int(ql) in NODES:
        add(f"Junction {ql}", int(ql), "junction")

    if GRAPH == "openstreetmap" and os.environ.get("GEOCODER", "on") != "off":
        try:
            if ql not in GEO_CACHE:
                GEO_CACHE[ql] = geocode_remote(q.strip())
            for g in GEO_CACHE[ql]:
                try:
                    add(str(g.get("display_name", q))[:90], nearest(float(g["lat"]), float(g["lon"])), "address")
                except (HTTPException, KeyError, ValueError):
                    continue
        except Exception as e:
            err = str(e)[:100]

    return dict(results=out[:10], geocoder_error=err, note="Addresses are snapped to the nearest junction of the loaded road network.")

# ---------- 12. Model Retraining on Logged Live Readings ----------
LIVE_MODEL = dict(model=None, metrics=None)

@app.post("/api/admin/retrain")
def retrain(a=Depends(need("admin", strict=True))):
    need_n = int(os.environ.get("MIN_LIVE_OBS", "500"))
    with db() as c:
        rows = [
            r for r in c.execute(
                "SELECT road_id,observed_at,load FROM traffic_observations WHERE data_source='tomtom_live' ORDER BY observed_at,id"
            )
            if r["road_id"] in EDGES
        ]
    if len(rows) < need_n:
        raise HTTPException(409, f"Need {need_n} live observations, have {len(rows)}. Run in live mode for longer.")

    def f(r):
        t = dt.datetime.fromisoformat(r["observed_at"])
        return [r["road_id"], EDGES[r["road_id"]]["centrality"], t.hour, t.weekday()]

    X_live = np.array([f(r) for r in rows], float)
    y_live = np.array([r["load"] for r in rows])
    k = int(len(rows) * 0.8)

    m = RandomForestRegressor(n_estimators=60, max_depth=10, random_state=0, n_jobs=1).fit(X_live[:k], y_live[:k])
    by = {}
    for rid, v in zip(X_live[:k, 0], y_live[:k]):
        by.setdefault(int(rid), []).append(v)
    glob = float(y_live[:k].mean())
    pb = np.array([np.mean(by[int(r)]) if int(r) in by else glob for r in X_live[k:, 0]])
    pr = m.predict(X_live[k:])

    sc = lambda p: dict(
        MAE=round(float(np.mean(abs(p - y_live[k:]))), 4),
        RMSE=round(float(np.sqrt(np.mean((p - y_live[k:]) ** 2))), 4)
    )
    res = dict(
        random_forest=sc(pr),
        baseline_road_mean=sc(pb),
        n_train=k,
        n_test=len(rows) - k,
        data_source="LIVE observations (TomTom)"
    )
    res["beats_baseline"] = res["random_forest"]["MAE"] < res["baseline_road_mean"]["MAE"]
    LIVE_MODEL.update(model=m, metrics=res)
    with db() as c:
        audit(c, a["id"], f"retrained on {len(rows)} live observations")
    return res

# ---------- 13. Hardening & Security Middleware ----------
RATE = {
    "login": int(os.environ.get("RATE_LOGIN_PER_MIN", "20")),
    "api": int(os.environ.get("RATE_API_PER_MIN", "300"))
}
HITS: Dict[Tuple[str, bool], List[float]] = {}

@app.middleware("http")
async def guard(request: Request, call_next):
    ip = request.client.host if request.client else "?"
    strict = request.url.path in ("/api/login", "/api/register")
    key = (ip, strict)
    t = time.time()
    q = [x for x in HITS.get(key, []) if t - x < 60]
    if len(q) >= RATE["login" if strict else "api"]:
        HITS[key] = q
        return JSONResponse({"detail": "Rate limit exceeded, try again in a minute"}, status_code=429)
    HITS[key] = q + [t]

    response = await call_next(request)
    response.headers.update({
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Content-Security-Policy": "default-src 'self' 'unsafe-inline' https://unpkg.com https://cdn.jsdelivr.net data:;"
    })
    return response

@app.get("/api/health")
def health():
    with db() as c:
        c.execute("SELECT 1")
    return dict(ok=True, traffic=source(), graph=GRAPH)

# ---------- 14. Static Pages & Frontend Mounting ----------
BASE_DIR = Path(__file__).resolve().parent
FRONTEND_CANDIDATES = [
    Path(os.environ.get("FRONTEND_DIR", "")),
    BASE_DIR.parent / "frontend",
    BASE_DIR / "frontend",
    BASE_DIR / "static",
    BASE_DIR.parent / "static",
]
FRONTEND_DIR = next((d for d in FRONTEND_CANDIDATES if d and d.is_dir()), BASE_DIR / "static")

def _page(name: str):
    p = FRONTEND_DIR / name
    if not p.is_file():
        p = BASE_DIR / "static" / name
    if not p.is_file():
        p = BASE_DIR.parent / "static" / name
    return FileResponse(str(p))

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

@app.get("/")
def landing_page(): return _page("landing.html")

@app.get("/app")
def dashboard_app(): return _page("index.html")

@app.get("/pending")
def pending_page(): return _page("pending.html")

@app.get("/analysis")
def analysis_page(): return _page("analysis.html")

@app.get("/history")
def history_page(): return _page("history.html")

# Dedicated standalone pages
@app.get("/login")
def page_login(): return _page("login.html")

@app.get("/register")
def page_register(): return _page("register.html")

@app.get("/map")
def page_map(): return _page("map.html")

@app.get("/route-compare")
def page_route_compare(): return _page("route_compare.html")

@app.get("/traffic-prediction")
def page_traffic_prediction(): return _page("traffic_prediction.html")

@app.get("/transit-planning")
def page_transit_planning(): return _page("transit_planning.html")

@app.get("/scenarios")
def page_scenarios(): return _page("scenarios.html")

@app.get("/reports")
def page_reports(): return _page("reports.html")

@app.get("/ambulance-dashboard")
def page_ambulance_dashboard(): return _page("ambulance_dashboard.html")

@app.get("/bus-dashboard")
def page_bus_dashboard(): return _page("bus_dashboard.html")

@app.get("/admin-dashboard")
def page_admin_dashboard(): return _page("admin_dashboard.html")
