"""Road network graph representation and routing algorithms (A* and Dijkstra).
Supports real OpenStreetMap networks (default: Anna Nagar, Chennai) and simulated 6x6 grid test fixtures.
Supports static, current traffic-aware, and time-dependent predicted traffic routing.
"""
import os, json, math, heapq
from typing import Dict, List, Tuple, Any, Optional

class RoadNetwork:
    def __init__(self, network_file: Optional[str] = None):
        self.network_file = network_file or os.environ.get("NETWORK_FILE", "network.json")
        self.nodes: Dict[int, Tuple[float, float]] = {}
        self.edges: Dict[int, Dict[str, Any]] = {}
        self.adj: Dict[int, List[Tuple[int, int]]] = {}
        self.hospitals: Dict[int, Tuple[str, int]] = {}
        self.bbox: Tuple[float, float, float, float] = (0, 0, 0, 0)
        self.graph_type = "simulated-grid"
        self.vmax = 50.0
        self.area_name = "Simulated 6x6 Grid"
        
        self.load_graph()

    def hav(self, a: int, b: int) -> float:
        """Great-circle distance (km) between junctions a and b using Haversine formula."""
        (la1, lo1), (la2, lo2) = self.nodes[a], self.nodes[b]
        p = math.pi / 180.0
        h = math.sin((la2 - la1) * p / 2.0) ** 2 + math.cos(la1 * p) * math.cos(la2 * p) * math.sin((lo2 - lo1) * p / 2.0) ** 2
        return 12742.0 * math.asin(math.sqrt(max(0.0, min(1.0, h))))

    def load_graph(self):
        # Check if real OSM network file exists and is not suppressed by grid test fixture
        use_grid = (self.network_file == "__grid_test_fixture__" or 
                    os.environ.get("USE_GRID_FIXTURE") == "1" or 
                    not os.path.exists(self.network_file))
        
        if not use_grid and os.path.exists(self.network_file):
            with open(self.network_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.graph_type = "openstreetmap"
            self.area_name = data.get("area", "Anna Nagar, Chennai, India")
            self.nodes = {int(k): (float(v[0]), float(v[1])) for k, v in data["nodes"].items()}
            self.edges = {}
            self.adj = {n: [] for n in self.nodes}
            
            # Compute center and max distance for centrality heuristic
            cl = sum(v[0] for v in self.nodes.values()) / max(len(self.nodes), 1)
            co = sum(v[1] for v in self.nodes.values()) / max(len(self.nodes), 1)
            far = max(abs(v[0] - cl) + abs(v[1] - co) for v in self.nodes.values()) or 1.0
            
            for item in data["edges"]:
                a, b, km, sp = item[0], item[1], float(item[2]), float(item[3])
                eid = len(self.edges)
                mid = [(self.nodes[a][k] + self.nodes[b][k]) / 2.0 for k in (0, 1)]
                centrality = 1.0 - (abs(mid[0] - cl) + abs(mid[1] - co)) / far
                self.edges[eid] = {
                    "id": eid, "a": a, "b": b, "km": km, "speed": sp,
                    "centrality": round(centrality, 4),
                    "name": f"Road {eid} ({a} <-> {b})"
                }
                self.adj[a].append((b, eid))
                self.adj[b].append((a, eid))
                
            raw_hosp = data.get("hospitals", [])
            self.hospitals = {i + 1: (h[0], int(h[1])) for i, h in enumerate(raw_hosp[:4])}
            
            lats = [v[0] for v in self.nodes.values()]
            lons = [v[1] for v in self.nodes.values()]
            self.bbox = (min(lats), min(lons), max(lats), max(lons))
        else:
            # 6x6 grid city test fixture
            self.graph_type = "simulated-grid"
            self.area_name = "Synthetic 6x6 Grid City"
            N, LAT0, LON0, STEP = 6, 13.00, 80.20, 0.01
            self.nodes = {r * N + c: (round(LAT0 + r * STEP, 6), round(LON0 + c * STEP, 6))
                          for r in range(N) for c in range(N)}
            self.edges = {}
            self.adj = {n: [] for n in self.nodes}
            for r in range(N):
                for c in range(N):
                    a = r * N + c
                    for b in ([a + 1] if c < N - 1 else []) + ([a + N] if r < N - 1 else []):
                        arterial = (r in (2, 3) and b == a + 1) or (c in (2, 3) and b == a + N)
                        eid = len(self.edges)
                        dist_km = self.hav(a, b)
                        cent = 1.0 - (abs((self.nodes[a][0] + self.nodes[b][0]) / 2.0 - 13.025) +
                                      abs((self.nodes[a][1] + self.nodes[b][1]) / 2.0 - 80.225)) / 0.05
                        self.edges[eid] = {
                            "id": eid, "a": a, "b": b, "km": dist_km,
                            "speed": 50.0 if arterial else 30.0,
                            "centrality": round(cent, 4),
                            "name": f"Grid Street {eid}"
                        }
                        self.adj[a].append((b, eid))
                        self.adj[b].append((a, eid))
            self.hospitals = {1: ("City Hospital", 35), 2: ("Central Hospital", 14), 3: ("North General", 5)}
            self.bbox = (LAT0, LON0, LAT0 + (N - 1) * STEP, LON0 + (N - 1) * STEP)

    def t_free(self, edge: Dict[str, Any]) -> float:
        """Free-flow traversal time in minutes."""
        return edge["km"] / edge["speed"] * 60.0

    def t_loaded(self, edge: Dict[str, Any], load_x: float, bypass: float = 0.0) -> float:
        """BPR Congestion function: t = t_free * (1 + 0.15 * x^4 * (1 - bypass)).
        load_x = volume-to-capacity ratio.
        bypass = emergency queue bypass share (critical: 0.5, urgent: 0.25, routine: 0.0).
        """
        return self.t_free(edge) * (1.0 + 0.15 * (load_x ** 4) * (1.0 - bypass))

    def search(
        self,
        src: int,
        dst: int,
        algo: str = "astar",
        mode: str = "aware",
        loads: Optional[Dict[int, float]] = None,
        bypass: float = 0.0,
        departure_hour: Optional[float] = None,
        dow: int = 1,
        predictor: Any = None
    ) -> Tuple[List[int], List[int], int]:
        """Dijkstra or A* search with static, traffic-aware, or time-dependent costs.
        Returns: (path_nodes, path_edges, nodes_expanded)
        """
        if src not in self.nodes:
            raise ValueError(f"Unknown source junction {src}")
        if dst not in self.nodes:
            raise ValueError(f"Unknown destination junction {dst}")
        if src == dst:
            return [src], [], 0

        # Heuristic for A* (admissible & consistent)
        if mode == "static":
            h_func = lambda n: self.hav(n, dst)
        else:
            h_func = lambda n: (self.hav(n, dst) / self.vmax) * 60.0 # free-flow minimum time heuristic

        h = h_func if algo == "astar" else (lambda n: 0.0)

        # Priority queue: (f_score, node_id)
        pq = [(h(src), src)]
        g_score: Dict[int, float] = {src: 0.0}
        prev: Dict[int, Tuple[int, int]] = {}
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

            for v, eid in self.adj[u]:
                edge = self.edges[eid]
                
                # Determine edge cost:
                if mode == "static":
                    cost = edge["km"]
                elif departure_hour is not None and predictor is not None:
                    # Time-dependent predicted traffic!
                    arrival_hour = (departure_hour + g_score[u] / 60.0) % 24.0
                    pred_load = predictor.predict_edge(eid, arrival_hour, dow)
                    cost = self.t_loaded(edge, pred_load, bypass)
                else:
                    cur_load = loads.get(eid, 0.0) if loads else 0.0
                    cost = self.t_loaded(edge, cur_load, bypass)

                ng = g_score[u] + cost
                if ng < g_score.get(v, 1e18):
                    g_score[v] = ng
                    prev[v] = (u, eid)
                    heapq.heappush(pq, (ng + h(v), v))

        if dst not in prev:
            raise ValueError(f"No path between {src} and {dst}")

        path, eids, curr = [dst], [], dst
        while curr != src:
            curr, eid = prev[curr]
            eids.append(eid)
            path.append(curr)

        return path[::-1], eids[::-1], expanded

    def summarize(
        self,
        path: List[int],
        eids: List[int],
        loads: Dict[int, float],
        expanded: Optional[int] = None,
        bypass: float = 0.0
    ) -> Dict[str, Any]:
        """Summarize calculated route: path, coordinates, minutes, km, cumulative breakdown."""
        mins = [self.t_loaded(self.edges[i], loads.get(i, 0.0), bypass) for i in eids]
        return {
            "path": path,
            "coords": [self.nodes[n] for n in path],
            "minutes": round(sum(mins), 2),
            "km": round(sum(self.edges[i]["km"] for i in eids), 2),
            "expanded": expanded,
            "cumulative": [round(sum(mins[:k]), 2) for k in range(len(mins) + 1)]
        }

    def nearest_node(self, lat: float, lon: float) -> int:
        """Find the nearest network junction to the given coordinates."""
        b = self.bbox
        # Allow 0.02 deg margin around network bounding box
        if not (b[0] - 0.02 <= lat <= b[2] + 0.02 and b[1] - 0.02 <= lon <= b[3] + 0.02):
            raise ValueError("Location outside loaded network area")
        return min(self.nodes, key=lambda n: (self.nodes[n][0] - lat) ** 2 + (self.nodes[n][1] - lon) ** 2)

    def candidate_bus_corridors(self) -> Dict[str, List[int]]:
        """Compute two candidate transit corridors on the network."""
        if self.graph_type == "simulated-grid":
            return {
                "Route A (direct)": [12, 13, 14, 15, 16, 17],
                "Route B (detour via row 3)": [12, 18, 19, 20, 21, 22, 23, 17]
            }
        else:
            # On real OSM network: corridor across Anna Nagar
            o = min(self.nodes, key=lambda n: sum(self.nodes[n]))
            d = max(self.nodes, key=lambda n: self.hav(o, n))
            L0 = {i: 0.0 for i in self.edges}
            p1, e1, _ = self.search(o, d, "astar", "static", L0)
            L_alt = {i: (2.0 if i in e1 else 0.0) for i in self.edges}
            p2, _, _ = self.search(o, d, "astar", "aware", L_alt)
            return {
                "Corridor A (Main Trunk Arterial)": p1,
                "Corridor B (Alternative Detour)": p2
            }
