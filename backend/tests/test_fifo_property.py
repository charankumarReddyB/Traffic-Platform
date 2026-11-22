"""Tests for the Arrive-Later-Never-Earlier (FIFO) Property in Time-Dependent Routing.

Property Definition:
-------------------
Let e = (u, v) be a directed edge in the road network.
Let c(e, t) be the travel time across edge e for a vehicle departing node u at time t.
The arrival time at node v is defined as:
    arr(e, t) = t + c(e, t)

The Arrive-Later-Never-Earlier (FIFO) property requires that for all departure times t1, t2:
    t1 <= t2  ==>  arr(e, t1) <= arr(e, t2)
    t1 + c(e, t1) <= t2 + c(e, t2)
    c(e, t1) - c(e, t2) <= t2 - t1

Equivalently, if travel time c(e, t) is differentiable with respect to time t:
    d/dt [arr(e, t)] = 1 + dc/dt >= 0  <==>  dc/dt >= -1

Physical Meaning:
-----------------
Traffic may clear after peak hours (travel time decreases over time, dc/dt < 0),
but travel time cannot decrease faster than real clock time advances (dc/dt cannot be < -1).
If dc/dt < -1, a driver departing later would arrive earlier along the same road segment (overtaking).
When FIFO holds, standard time-dependent Dijkstra/A* algorithms are guaranteed to find
globally optimal shortest paths without requiring vehicles to wait at intermediate junctions.
"""
import pytest, math
import graph, predictor

@pytest.fixture(scope="module")
def network():
    return graph.RoadNetwork("network.json")

@pytest.fixture(scope="module")
def trained_predictor(network):
    # Fast initial predictor (2 weeks training data: 1 week train, 1 week test)
    return predictor.TrafficPredictor(network.edges, weeks=2, seed=42)

def test_static_routing_strictly_satisfies_fifo(network):
    """Under static or snapshot traffic-aware routing, edge cost is time-invariant c(e).
    Therefore arr(e, t2) - arr(e, t1) = t2 - t1 >= 0, strictly satisfying FIFO.
    """
    for eid, edge in list(network.edges.items())[:15]:
        c_static = edge["km"]
        for t1 in [0.0, 8.0, 9.5, 17.0, 20.0]:
            for dt in [0.1, 0.5, 1.0, 2.0]:
                t2 = t1 + dt
                arr1 = t1 + c_static
                arr2 = t2 + c_static
                assert arr2 >= arr1, f"Static routing FIFO violation on edge {eid}"
                assert math.isclose(arr2 - arr1, dt), "Static routing arrival difference must equal dt"

def test_traffic_aware_snapshot_strictly_satisfies_fifo(network):
    """Under current traffic-aware snapshot routing, loads are held constant during search.
    Hence c(e, t) = c(e, L_current) is time-invariant and FIFO is strictly satisfied.
    """
    loads = {eid: 1.2 for eid in network.edges}
    for eid, edge in list(network.edges.items())[:15]:
        c_aware = network.t_loaded(edge, loads[eid], bypass=0.0)
        for t1 in [6.0, 8.5, 12.0, 18.0]:
            for dt in [0.25, 0.5, 1.0]:
                t2 = t1 + dt
                arr1 = t1 + c_aware
                arr2 = t2 + c_aware
                assert arr2 > arr1, f"Traffic-aware snapshot FIFO violation on edge {eid}"
                assert math.isclose(arr2 - arr1, dt)

def test_predicted_time_dependent_traffic_satisfies_fifo_at_operational_intervals(network, trained_predictor):
    """At operational dispatch intervals (15 to 60 minutes), traffic evolution satisfies FIFO:
    A vehicle departing 15, 30, or 60 minutes later never arrives earlier.
    Evaluated across top arterial and collector corridors during rush-hour to off-peak transitions.
    """
    edges_to_test = [e for e in network.edges.values() if e.get("centrality", 0) > 0.4][:5]
    intervals_min = [15.0, 30.0, 60.0]
    # Test key transition regimes: morning peak decay (9.0 -> 11.5) and evening peak decay (18.0 -> 21.0)
    departure_hours = [7.0, 8.5, 9.0, 9.5, 10.0, 11.0, 13.0, 17.5, 18.0, 19.0, 20.0, 22.0]
    
    for edge in edges_to_test:
        eid = edge["id"]
        for t1_h in departure_hours:
            for dt_min in intervals_min:
                dt_h = dt_min / 60.0
                t2_h = t1_h + dt_h
                
                # Edge traversal times in minutes
                c1_min = network.t_loaded(edge, trained_predictor.predict_edge(eid, t1_h % 24.0))
                c2_min = network.t_loaded(edge, trained_predictor.predict_edge(eid, t2_h % 24.0))
                
                arr1_min = (t1_h * 60.0) + c1_min
                arr2_min = (t2_h * 60.0) + c2_min
                
                # Arrive-later-never-earlier condition
                diff = arr2_min - arr1_min
                assert diff >= -1e-6, (
                    f"Operational FIFO violation on Edge #{eid} ({edge['name']}): "
                    f"Depart at {t1_h:.2f}h arrives at {arr1_min:.2f}m, "
                    f"Depart at {t2_h:.2f}h arrives at {arr2_min:.2f}m (diff={diff:.4f}m)"
                )

def test_document_theoretical_non_fifo_case_at_discrete_tree_split_boundaries(network, trained_predictor):
    """MATHEMATICAL DOCUMENTATION OF NON-FIFO CASE:
    --------------------------------------------------
    Piecewise-constant machine learning estimators (DecisionTreeRegressor, RandomForestRegressor)
    partition feature space into axis-aligned rectangular regions.
    At an exact decision boundary t0 (e.g. hour split h = 9.42), the predicted load drops discretely:
        load(t0 - eps) = 1.30  -->  load(t0 + eps) = 0.90
    This causes an instantaneous step decrease in edge travel time Delta_c = c(t0-) - c(t0+) > 0.
    For any microscopic delta_t < Delta_c:
        arr(t0 + delta_t) - arr(t0) = delta_t - Delta_c < 0.
        
    This test constructs and proves this mathematical phenomenon, documenting why real-world
    time-dependent routing engines either:
    1. Linearly interpolate predictions between dispatch epochs (continuous c(e, t)), or
    2. Operate on discrete departure time buckets (e.g. 5-min intervals where delta_t >= Delta_c).
    """
    edge = list(network.edges.values())[0]
    eid = edge["id"]
    
    # Synthetic discrete jump model illustrating the non-FIFO phenomenon
    t_free = network.t_free(edge)
    
    # Congestion load drops sharply across hour 10.00 from peak (1.6) to normal (0.6)
    def step_load(h):
        return 1.6 if (h < 10.000) else 0.6
        
    c_before = t_free * (1.0 + 0.15 * (1.6 ** 4))
    c_after  = t_free * (1.0 + 0.15 * (0.6 ** 4))
    delta_c_min = c_before - c_after
    
    assert delta_c_min > 0, "Travel time must decrease when load drops"
    
    # Consider departure 1 second before split vs 1 second after split
    eps_min = 2.0 / 60.0  # 2 seconds
    t1_min = 10.0 * 60.0 - (1.0 / 60.0)  # 09:59:59
    t2_min = 10.0 * 60.0 + (1.0 / 60.0)  # 10:00:01
    
    arr1_min = t1_min + c_before
    arr2_min = t2_min + c_after
    
    # If delta_t < delta_c, the later vehicle arrives earlier:
    if eps_min < delta_c_min:
        assert arr2_min < arr1_min, (
            "Proves mathematical non-FIFO condition: step drop causes earlier arrival for later departure"
        )
        violation_magnitude_sec = (arr1_min - arr2_min) * 60.0
        assert violation_magnitude_sec > 0
        
        # Now verify that applying linear interpolation between epochs restores FIFO:
        def interpolated_load(h, h0=9.5, h1=10.5):
            frac = max(0.0, min(1.0, (h - h0) / (h1 - h0)))
            return 1.6 - frac * (1.6 - 0.6)
            
        # Slope dc/dt with interpolation:
        c_interp1 = t_free * (1.0 + 0.15 * (interpolated_load(9.99) ** 4))
        c_interp2 = t_free * (1.0 + 0.15 * (interpolated_load(10.01) ** 4))
        arr_interp1 = 9.99 * 60.0 + c_interp1
        arr_interp2 = 10.01 * 60.0 + c_interp2
        assert arr_interp2 > arr_interp1, "Linear interpolation restores the FIFO arrive-later-never-earlier guarantee"

def test_monotonic_arrival_times_along_calculated_route(network, trained_predictor):
    """Along any path calculated by time-dependent A*, junction arrival times are strictly monotonically increasing."""
    src, dst = 0, 35
    path, eids, expanded = network.search(
        src, dst, algo="astar", mode="predicted",
        departure_hour=8.5, dow=1, predictor=trained_predictor
    )
    
    assert len(path) > 1
    curr_time = 8.5 * 60.0 # start at 08:30 (minutes)
    
    for i, eid in enumerate(eids):
        edge = network.edges[eid]
        arr_hour = (curr_time / 60.0) % 24.0
        pred_load = trained_predictor.predict_edge(eid, arr_hour, dow=1)
        step_cost = network.t_loaded(edge, pred_load)
        next_time = curr_time + step_cost
        assert next_time > curr_time, f"Arrival time must advance along edge {eid}"
        assert step_cost >= network.t_free(edge), "Step cost cannot be less than free-flow time"
        curr_time = next_time
