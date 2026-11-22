import os, sys, tempfile
os.environ.setdefault("TRAFFIC_DB", os.path.join(tempfile.mkdtemp(), "x.db")); os.environ.setdefault("ADMIN_PASSWORD", "x")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "experiments"))
import numpy as np, partial_info as pi

def test_regret_is_never_negative_and_all_info_current_gives_zero():
    res = pi.run_experiment(trials=25, seed=3, ks=(5,), intervals=(0.001, 30))
    assert all(min(v) > -1e-9 for k, v in res.items() if k[1] != "full_time")           # full information is optimal by construction
    assert max(res[("car", "all_roads", len(pi.main.EDGES), 0.001)]) < 1e-6              # all roads, ~0 minutes old == full information
    assert np.mean(res[("car", "all_roads", len(pi.main.EDGES), 30)]) >= 0

def test_deterministic_and_paired():
    a, b = pi.run_experiment(trials=10, seed=5, ks=(5,), intervals=(10,)), pi.run_experiment(trials=10, seed=5, ks=(5,), intervals=(10,))
    assert a == b and len({len(v) for v in a.values()}) == 1                             # same results for same seed; every config sees the same trials

def test_summary_fields():
    rows = pi.summarise(pi.run_experiment(trials=15, seed=1, ks=(5,), intervals=(10,)), 1, boot=100)
    assert rows and all(r["data_source"] == "SIMULATED" and r["ci_lo"] <= r["mean_regret_min"] <= r["ci_hi"] for r in rows)
