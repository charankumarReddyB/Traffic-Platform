"""Live traffic ingestion and congestion classification service.
Samples live TomTom Traffic Flow speeds for prioritized roads, maps speed ratio to green/yellow/red congestion,
logs all readings to database, and enforces API quota limits.
"""
import os, time, json, urllib.request, urllib.parse, datetime as dt
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Tuple, Any, Optional
import numpy as np

def speed_to_load(cur: float, free: float) -> float:
    """Inverts BPR model so modelled time ratio == observed free/current speed ratio."""
    if cur >= free:
        return 0.0
    return float(np.clip(((free / max(cur, 1.0) - 1.0) / 0.15) ** 0.25, 0.0, 2.0))

def speed_to_congestion_level(cur: float, free: float) -> str:
    """Documented thresholds:
    ratio = currentSpeed / freeFlowSpeed:
      green:  ratio >= 0.75 (Free-flow / Normal)
      yellow: 0.50 <= ratio < 0.75 (Moderate delay)
      red:    ratio < 0.50 (Severe congestion / Gridlock)
    """
    if free <= 0.0:
        return "green"
    ratio = cur / free
    if ratio >= 0.75:
        return "green"
    elif ratio >= 0.50:
        return "yellow"
    else:
        return "red"

def fetch_flow(lat: float, lon: float, api_key: str) -> Tuple[float, float]:
    """Fetch live Flow Segment Data from TomTom API.
    Key read strictly from environment variable, never logged.
    """
    q = urllib.parse.urlencode({
        "point": f"{lat},{lon}",
        "key": api_key,
        "unit": "KMPH"
    })
    url = f"https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json?{q}"
    req = urllib.request.Request(url, headers={"User-Agent": "UrbanTrafficPlatform/1.0"})
    with urllib.request.urlopen(req, timeout=6) as response:
        data = json.load(response)["flowSegmentData"]
    return float(data["currentSpeed"]), float(data["freeFlowSpeed"])

class LiveTrafficManager:
    def __init__(self, road_network):
        self.network = road_network
        self.live_loads: Dict[int, float] = {}
        self.live_speeds: Dict[int, Dict[str, Any]] = {}
        self.last_refresh_time: float = 0.0
        self.last_error: Optional[str] = None
        self.daily_requests_used: int = 0
        self.last_reset_day: int = time.gmtime().tm_yday
        self.overrides: set = set()

    def get_source(self) -> str:
        return os.environ.get("TRAFFIC_SOURCE", "simulated").lower()

    def _check_day_reset(self):
        cur_day = time.gmtime().tm_yday
        if cur_day != self.last_reset_day:
            self.daily_requests_used = 0
            self.last_reset_day = cur_day

    def refresh_live(self, db_log_callback=None) -> Dict[str, Any]:
        """Sample prioritized roads up to quota limit."""
        self.last_refresh_time = time.time()
        self._check_day_reset()
        
        api_key = os.environ.get("TOMTOM_API_KEY", "").strip()
        if not api_key:
            self.last_error = "TOMTOM_API_KEY not set"
            self.live_loads = {}
            self.live_speeds = {}
            return self.get_status()

        # Prioritize top major roads by network centrality
        max_edges = int(os.environ.get("LIVE_MAX_EDGES", "15"))
        sorted_edges = sorted(self.network.edges.values(), key=lambda e: -e["centrality"])[:max_edges]

        # Quota check: 2,500 per day free tier
        quota_limit = int(os.environ.get("TOMTOM_QUOTA_PER_DAY", "2500"))
        if self.daily_requests_used + len(sorted_edges) > quota_limit:
            self.last_error = f"Daily quota threshold reached ({self.daily_requests_used}/{quota_limit})"
            return self.get_status()

        def fetch_one(edge):
            a, b = edge["a"], edge["b"]
            mid_lat = (self.network.nodes[a][0] + self.network.nodes[b][0]) / 2.0
            mid_lon = (self.network.nodes[a][1] + self.network.nodes[b][1]) / 2.0
            try:
                cur, free = fetch_flow(mid_lat, mid_lon, api_key)
                return edge["id"], cur, free, None
            except Exception as ex:
                return edge["id"], 0.0, 0.0, str(ex)[:80]

        with ThreadPoolExecutor(max_workers=6) as executor:
            results = list(executor.map(fetch_one, sorted_edges))

        self.daily_requests_used += len(sorted_edges)
        ok_results = [r for r in results if r[3] is None]

        if ok_results:
            self.live_loads = {eid: speed_to_load(c, f) for eid, c, f, _ in ok_results}
            self.live_speeds = {
                eid: {
                    "current_kmh": round(c, 1),
                    "free_kmh": round(f, 1),
                    "load": round(self.live_loads[eid], 2),
                    "level": speed_to_congestion_level(c, f)
                }
                for eid, c, f, _ in ok_results
            }
            self.last_error = None
        else:
            self.last_error = results[0][3] if results else "No roads sampled"

        # Log observations to database via callback
        if db_log_callback and ok_results:
            now_iso = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
            obs_rows = [
                {
                    "road_id": eid,
                    "observed_at": now_iso,
                    "speed_kmh": round(c, 1),
                    "free_speed_kmh": round(f, 1),
                    "load": round(self.live_loads[eid], 3),
                    "congestion_level": speed_to_congestion_level(c, f),
                    "data_source": "tomtom_live"
                }
                for eid, c, f, _ in ok_results
            ]
            db_log_callback(obs_rows)

        return self.get_status()

    def get_effective_loads(self, fallback_loads: Dict[int, float], db_log_callback=None) -> Dict[int, float]:
        """Combine modelled loads, live telemetry, and admin scenario overrides."""
        L = dict(fallback_loads)
        
        # In live mode: check TTL and refresh if expired
        if self.get_source() == "live":
            ttl = int(os.environ.get("LIVE_TTL_SECONDS", "600"))
            if time.time() - self.last_refresh_time > ttl:
                self.refresh_live(db_log_callback)
            for eid, v in self.live_loads.items():
                if eid not in self.overrides:
                    L[eid] = v

        # Admin overrides for scenario testing take highest precedence
        for eid in self.overrides:
            L[eid] = 1.8

        return L

    def get_status(self) -> Dict[str, Any]:
        n = len(self.live_loads)
        mode = self.get_source()
        total = len(self.network.edges)
        age_sec = round(time.time() - self.last_refresh_time, 1) if self.last_refresh_time else None

        if mode != "live":
            label = "SIMULATED traffic (synthetic load profile)"
        elif n > 0:
            label = f"LIVE traffic on {n} of {total} roads ({age_sec}s ago; others modelled)"
        else:
            label = f"LIVE mode unavailable ({self.last_error or 'not refreshed yet'}) - showing SIMULATED"

        return {
            "mode": mode,
            "live_roads": n,
            "total_roads": total,
            "graph": self.network.graph_type,
            "area": self.network.area_name,
            "label": label,
            "data_age_seconds": age_sec,
            "error": self.last_error,
            "last_refresh": dt.datetime.fromtimestamp(self.last_refresh_time, dt.timezone.utc).isoformat(timespec="seconds") if self.last_refresh_time else None,
            "daily_requests_used": self.daily_requests_used,
            "daily_quota": 2500,
            "thresholds": {
                "green": "Speed ratio >= 0.75 (Free-flow / Normal)",
                "yellow": "0.50 <= Speed ratio < 0.75 (Moderate delay)",
                "red": "Speed ratio < 0.50 (Severe congestion / Gridlock)"
            }
        }
