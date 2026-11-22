"""Applied study: how much of the benefit of traffic-aware routing survives when live data covers only K roads and is stale?
ALL DATA IS SIMULATED (synthetic grid, synthetic incidents). Results say nothing about a real city until run on real data.
Usage: python experiments/partial_info.py --trials 150 --out experiments/results.csv
Design: every trial has ONE ground-truth traffic state at trip time t0 plus short-lived incidents. Each information regime gets
the SAME trials (paired). Router = A* on its believed loads; the chosen route is always SCORED under the true loads.
regret = time(route chosen under regime) - time(route chosen with full, current information) >= 0.
benefit_retained = 1 - mean_regret(regime) / mean_regret(no live data).
CAUTION on quota: 'central' and 'random' sample K roads ONCE per refresh for ALL users; 'on_route' needs K lookups per TRIP (on demand),
so it is not comparable at equal API quota. 'all_roads' ignores quota and is the upper bound for a given staleness."""
import os, sys, argparse, tempfile, csv
os.environ.setdefault("TRAFFIC_DB", os.path.join(tempfile.mkdtemp(), "exp.db")); os.environ.setdefault("ADMIN_PASSWORD", "experiment-only")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import main

VEH = {"car": 0.0, "ambulance_critical": main.BYPASS["critical"]}   # bus routes are fixed, so rerouting value does not apply
def plan(src, dst, L, b): return main.search(src, dst, "astar", "aware", L, b)[1]
def cost(eids, L, b): return sum(main.t_loaded(main.EDGES[i], L[i], b) for i in eids)

def run_experiment(trials=100, seed=0, ks=(5, 15, 40), intervals=(1, 5, 10, 30), n_inc=8, t0=60.0):
    rng = np.random.default_rng(seed); E = list(main.EDGES); nE = len(E); base = main.LOADS   # base = what the model predicts without live data
    central = sorted(E, key=lambda i: -main.EDGES[i]["centrality"]); ks = [k for k in ks if 0 < k < nE]; res = {}
    for _ in range(trials):
        noise = rng.normal(0, 0.05, nE); inc = {}
        for _i in range(n_inc):
            r = int(rng.choice(E)); s = rng.uniform(0, 100); inc.setdefault(r, []).append((s, s + rng.uniform(20, 90)))
        def val(i, t): return 1.8 if any(a <= t <= e for a, e in inc.get(i, [])) else float(np.clip(base[i] + noise[i], 0, 2))
        L_true = {i: val(i, t0) for i in E}
        obs = {iv: {i: val(i, t0 - rng.uniform(0, iv)) for i in E} for iv in intervals}        # each reading is up to iv minutes old
        src, dst = (int(x) for x in rng.choice(list(main.NODES), 2, replace=False)); perm = [int(x) for x in rng.permutation(E)]
        for v, b in VEH.items():
            t_full = cost(plan(src, dst, L_true, b), L_true, b); res.setdefault((v, "full_time", 0, 0), []).append(t_full)
            res.setdefault((v, "none", 0, 0), []).append(cost(plan(src, dst, base, b), L_true, b) - t_full)
            route = set(plan(src, dst, base, b)); onr = [e for e in perm if e in route]
            for iv in intervals:
                for strat, order in (("central", central), ("random", perm), ("on_route", onr)):
                    for k in ks:
                        info = dict(base); info.update({r: obs[iv][r] for r in order[:k]})
                        res.setdefault((v, strat, k, iv), []).append(cost(plan(src, dst, info, b), L_true, b) - t_full)
                res.setdefault((v, "all_roads", nE, iv), []).append(cost(plan(src, dst, obs[iv], b), L_true, b) - t_full)
    return res

def summarise(res, seed=0, boot=1000):
    rng = np.random.default_rng(seed + 1); rows = []
    for (v, strat, k, iv), r in sorted(res.items(), key=lambda x: x[0]):
        if strat == "full_time": continue
        r = np.array(r); none = np.array(res[(v, "none", 0, 0)]); idx = rng.integers(0, len(r), (boot, len(r)))
        m = r[idx].mean(1); n = none[idx].mean(1); ret = np.where(n > 1e-9, 1 - m / np.maximum(n, 1e-9), np.nan)
        m_sec = m * 60.0
        rows.append(dict(
            vehicle=v, strategy=strat, live_roads=k, interval_min=iv,
            mean_regret_min=round(float(r.mean()), 4),
            ci_lo=round(float(np.percentile(m, 2.5)), 4),
            ci_hi=round(float(np.percentile(m, 97.5)), 4),
            mean_regret_sec=round(float(r.mean() * 60.0), 2),
            ci_lo_sec=round(float(np.percentile(m_sec, 2.5)), 2),
            ci_hi_sec=round(float(np.percentile(m_sec, 97.5)), 2),
            benefit_retained=round(float(1 - r.mean() / none.mean()), 3) if none.mean() > 1e-9 else "",
            ret_lo=round(float(np.nanpercentile(ret, 2.5)), 3) if not np.all(np.isnan(ret)) else "",
            ret_hi=round(float(np.nanpercentile(ret, 97.5)), 3) if not np.all(np.isnan(ret)) else "",
            quota_comparable=(strat in ("central", "random", "all_roads")),
            trials=len(r), data_source="SIMULATED"
        ))
    return rows

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--trials", type=int, default=150)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--incidents", type=int, default=8)
    p.add_argument("--out", default="experiments/results.csv")
    a = p.parse_args()
    res = run_experiment(a.trials, a.seed, n_inc=a.incidents)
    rows = summarise(res, a.seed)
    
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    # Save all results to CSV
    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    # Also mirror to root experiments/results.csv if different
    root_out = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "experiments", "results.csv")
    if os.path.abspath(a.out) != os.path.abspath(root_out):
        try:
            os.makedirs(os.path.dirname(root_out), exist_ok=True)
            with open(root_out, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0]))
                w.writeheader()
                w.writerows(rows)
        except Exception:
            pass

    print("=" * 88)
    print("PARTIAL INFORMATION & STALE DATA STUDY (EQUAL-QUOTA COMPARISON)")
    print(f"Data Source: SIMULATED (Seed: {a.seed}, Trials: {a.trials}, Incidents: {a.incidents})")
    print("Road Network: Anna Nagar, Chennai (73 junctions, 103 edges)")
    print("=" * 88)
    print("[DISCLOSURE]: 'on_route' is DROPPED from quota comparison because it requires K queries")
    print("per individual trip rather than K queries per refresh interval for the entire city.")
    print("-" * 88)

    for v in VEH:
        t_sec = np.mean(res[(v, "full_time", 0, 0)]) * 60.0
        n_sec = np.mean(res[(v, "none", 0, 0)]) * 60.0
        print(f"\n== Vehicle: {v} | Mean Trip: {t_sec:.1f}s (Full Info) | Ignoring Live Data Costs: {n_sec:.1f}s ({100 * n_sec / max(t_sec, 1e-4):.1f}% regret) [{a.trials} trials]")
        print(f"{'Strategy':<12} {'Roads (K)':<10} {'Interval':<10} {'Regret (seconds) [95% CI]':<30} {'Benefit Retained [95% CI]'}")
        print("-" * 88)
        for r in rows:
            if r["vehicle"] == v and r["strategy"] != "none" and r["quota_comparable"]:
                regret_str = f"{r['mean_regret_sec']:>6.1f}s [{r['ci_lo_sec']:>5.1f}s, {r['ci_hi_sec']:>5.1f}s]"
                ret_str = f"{r['benefit_retained']:>5} [{r['ret_lo']}, {r['ret_hi']}]" if r['benefit_retained'] != "" else "N/A"
                print(f"{r['strategy']:<12} {r['live_roads']:>9} {r['interval_min']:>8}m {regret_str:<30} {ret_str}")

    print("\nSIMULATED data only. Wrote updated results to", a.out)
