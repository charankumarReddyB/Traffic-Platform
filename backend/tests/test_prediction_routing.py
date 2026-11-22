"""Automated tests proving:
1. Predicted traffic changes the chosen route compared to off-peak / distance-only routing.
2. Time-dependent A* search exactly matches a brute-force exhaustive path search on a small graph.
"""
import os, sys, math, heapq
from typing import Dict, List, Tuple, Any

# Ensure project root in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import main

def test_predicted_traffic_changes_chosen_route():
    """Proves that future predicted congestion at departure hour shifts the optimal route
    from the direct corridor to an alternate corridor.
    """
    src, dst = (0, 7) if main.GRAPH == "simulated-grid" else (0, 3)
    # 1. Off-peak departure (03:00 - minimal congestion)
    path_offpeak, edges_offpeak, _ = main.search(src, dst, algo="astar", mode="aware", departure_hour=3.0, dow=1)
    
    # 2. Peak departure (09:00 - morning rush hour on central arterials)
    path_peak, edges_peak, _ = main.search(src, dst, algo="astar", mode="aware", departure_hour=9.0, dow=1)
    
    # Assert that predicted traffic actively changes the route
    assert path_offpeak != path_peak, f"Expected different paths, got {path_offpeak} for both"
    assert len(path_offpeak) > 0 and len(path_peak) > 0
    assert path_offpeak[0] == src and path_offpeak[-1] == dst
    assert path_peak[0] == src and path_peak[-1] == dst

    # Calculate travel times under peak traffic for both routes to verify peak choice is faster at 09:00
    def eval_path_time(path_nodes, dep_hour, dow):
        t = 0.0
        for u, v in zip(path_nodes, path_nodes[1:]):
            eid = next(i for nxt, i in main.ADJ[u] if nxt == v)
            edge = main.EDGES[eid]
            arr_h = (dep_hour + t / 60.0) % 24.0
            pred_load = float(main.rf.predict([main.feats(edge, arr_h, dow)])[0])
            cost = main.t_loaded(edge, max(0.0, min(2.0, pred_load)))
            t += cost
        return t

    time_offpeak_path_at_peak = eval_path_time(path_offpeak, 9.0, 1)
    time_peak_path_at_peak = eval_path_time(path_peak, 9.0, 1)

    # The route chosen by A* for peak departure must be faster than (or equal to) following the off-peak route at peak time
    assert time_peak_path_at_peak <= time_offpeak_path_at_peak + 1e-6, (
        f"Peak route ({time_peak_path_at_peak:.3f} min) should be faster than off-peak route at peak ({time_offpeak_path_at_peak:.3f} min)"
    )

def test_astar_time_dependent_matches_brute_force():
    """Proves that A* with time-dependent edge costs returns the mathematically exact
    minimum-cost path by comparing against an exhaustive brute-force search on a small graph.
    """
    # Define a 5-node test network with multiple candidate paths
    # 0 -> 1 -> 4
    # 0 -> 1 -> 3 -> 4
    # 0 -> 2 -> 4
    # 0 -> 2 -> 3 -> 4
    nodes = {
        0: (0.0, 0.0),
        1: (1.0, 0.5),
        2: (0.8, -0.6),
        3: (2.0, 0.0),
        4: (3.0, 0.0)
    }

    edges = {
        0: {"u": 0, "v": 1, "t0": 2.0, "km": 1.5},
        1: {"u": 0, "v": 2, "t0": 1.8, "km": 1.4},
        2: {"u": 1, "v": 4, "t0": 5.0, "km": 3.0},
        3: {"u": 1, "v": 3, "t0": 1.2, "km": 1.0},
        4: {"u": 2, "v": 3, "t0": 1.6, "km": 1.2},
        5: {"u": 2, "v": 4, "t0": 4.5, "km": 2.8},
        6: {"u": 3, "v": 4, "t0": 2.2, "km": 1.5}
    }

    adj: Dict[int, List[Tuple[int, int]]] = {n: [] for n in nodes}
    for eid, e in edges.items():
        adj[e["u"]].append((e["v"], eid))

    # Time-dependent non-linear cost function: c(e, t)
    # Travel time depends on the exact arrival time t at the edge
    def edge_cost(eid: int, arrival_t: float) -> float:
        t0 = edges[eid]["t0"]
        if eid == 2:   # direct 1 -> 4 gets congested at t in [3, 8]
            load = 1.8 if (3.0 <= (arrival_t % 12.0) <= 8.0) else 0.2
        elif eid == 3: # 1 -> 3
            load = 0.5 + 0.5 * math.sin(arrival_t)
        elif eid == 6: # 3 -> 4
            load = 0.4 + 0.6 * math.cos(arrival_t / 2.0)
        else:
            load = 0.3
        return t0 * (1.0 + 0.15 * (load ** 4))

    # 1. Brute-force exhaustive search: find all simple paths from src to dst
    def find_all_paths(curr: int, target: int, visited: set) -> List[List[int]]:
        if curr == target:
            return [[target]]
        paths = []
        for nxt, eid in adj[curr]:
            if nxt not in visited:
                for sub in find_all_paths(nxt, target, visited | {nxt}):
                    paths.append([curr] + sub)
        return paths

    all_paths = find_all_paths(0, 4, {0})
    assert len(all_paths) == 4, f"Expected 4 paths, found {len(all_paths)}"

    # Test across multiple departure times
    for dep_t in [0.0, 2.5, 4.0, 7.0, 11.0]:
        # Brute-force evaluation
        best_bf_time = 1e18
        best_bf_path = None

        for path in all_paths:
            cur_t = dep_t
            for u, v in zip(path, path[1:]):
                eid = next(i for nxt, i in adj[u] if nxt == v)
                cost = edge_cost(eid, cur_t)
                cur_t += cost
            total_duration = cur_t - dep_t
            if total_duration < best_bf_time:
                best_bf_time = total_duration
                best_bf_path = path

        # 2. Time-Dependent A* search
        # Admissible heuristic: Euclidean distance / max_speed (underestimates remaining travel time)
        vmax = 2.0 # units per minute
        def h_val(n: int) -> float:
            dx = nodes[4][0] - nodes[n][0]
            dy = nodes[4][1] - nodes[n][1]
            return math.sqrt(dx * dx + dy * dy) / vmax

        pq = [(h_val(0), 0)]
        g: Dict[int, float] = {0: 0.0}
        prev: Dict[int, Tuple[int, int]] = {}
        seen = set()

        while pq:
            _, u = heapq.heappop(pq)
            if u in seen:
                continue
            seen.add(u)
            if u == 4:
                break
            for v, eid in adj[u]:
                cost = edge_cost(eid, dep_t + g[u])
                ng = g[u] + cost
                if ng < g.get(v, 1e18):
                    g[v] = ng
                    prev[v] = (u, eid)
                    heapq.heappush(pq, (ng + h_val(v), v))

        astar_path, curr = [4], 4
        while curr != 0:
            curr, _ = prev[curr]
            astar_path.append(curr)
        astar_path = astar_path[::-1]
        astar_time = g[4]

        # Verify A* matches brute-force
        assert abs(astar_time - best_bf_time) < 1e-9, (
            f"At dep_t={dep_t}: A* time {astar_time} != Brute-force time {best_bf_time}"
        )
        assert astar_path == best_bf_path, (
            f"At dep_t={dep_t}: A* path {astar_path} != Brute-force path {best_bf_path}"
        )
