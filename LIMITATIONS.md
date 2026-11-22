# Platform Limitations, Assumptions, and Simulation Disclosures

In accordance with **The Evidence Rule**, every limitation, synthetic component, and unverified edge case of the platform is explicitly enumerated below. No claim is made without accompanying automated verification or empirical test evidence.

---

## 1. Title Word Verification Matrix

| Title Keyword | Verified Production Feature | Automated Test or Experiment | Evidence (data source) | Explicit Limitations & Disclosures |
|---|---|---|---|---|
| **AI-Powered** | Random Forest ML regressor predicting future edge loads; time-dependent edge costs fed into A* router. | `tests/test_analysis.py`, `tests/test_hardening.py`, `tests/test_prediction_routing.py`. | **[SYNTHETIC]** Evaluated on chronological split: RF MAE 0.052, RMSE 0.071 vs Historical Mean MAE 0.089. Proven route divergence: 03:00 off-peak direct corridor shifts to 09:00 peak bypass. Exact cost match to exhaustive brute-force (< 1e-9 min). | Default baseline training uses synthetic temporal observations. Live-data retraining pipeline is verified with synthetic rows labelled as TomTom observations until real database reaches threshold (500 obs). |
| **Urban** | Real OpenStreetMap major drivable roads (trunk, primary, secondary, tertiary) in Anna Nagar, Chennai (73 junctions, 103 edges, 4 hospitals). | `build_network.py`, `test_live::test_real_graph_file_loads_and_routes`. | **[OSM EXTRACT]** `network.json` containing real OSM coordinates & real hospitals (Sundaram Medical Foundation, City Tower Hospitals, etc.). | Small residential service lanes and alleys are excluded to preserve search efficiency. The 6x6 grid is strictly preserved only as a regression test fixture. |
| **Traffic** | Live TomTom Traffic Flow Segment API polling with quota manager (<2,500/day), caching, and green/yellow/red congestion thresholds. | `tests/test_live.py::test_speed_to_load_matches_bpr`, `test_live_refresh_overrides_model_and_logs`, `experiments/test_live_tomtom.py`. | **[SIMULATED FALLBACK]** Live road count, data age in seconds, and DB observations logged in `traffic_observations`. When API key is absent, returns graceful `[BLOCKED BY EVIDENCE RULE]`. | **UNPROVEN ON THIS MACHINE**: Real live data requires a valid `TOMTOM_API_KEY`. Because no API key was configured in the environment (`KEY_PRESENT: False`), querying the live TomTom API remains unproven. The system explicitly announces `SIMULATED` traffic mode. |
| **Public Transport**| Real/sample bus corridors with ordered stops, stop delay calculations under live traffic, headway vs fleet check formula. | `tests/test_bus.py`, `tests/test_schedule.py`. | **[PARAMETRIC TIMETABLE]** Timetable generator, fleet sufficiency calculation: $\lceil \frac{2 \times \text{cycle}}{\text{headway}} \rceil$, proposal approval workflow. | Bus passenger boarding/alighting dwell times are approximated as fixed 30-second stop delays. Fleet schedules are operational estimates, not connected to physical GPS transponders on city buses. |
| **Emergency** | Ambulance operator console with 3 severity profiles (Critical 0.5, Urgent 0.25, Routine 0.0), browser GPS tracking, and trip state machine. | `tests/test_api.py::test_emergency_trip_lifecycle`, `tests/test_api.py::test_severity_profiles`. | **[SIMULATED SENSORS]** Live breadcrumb location updates stored in DB; emergency trip ETA comparison. | **ADVISORY RECOMMENDATION ONLY**: Ambulance trips never control traffic signal preemption, lane clearance, or other road users. Emergency siren queue bypass is a documented parametric assumption. |
| **Route Optimization**| A* with admissible Euclidean distance heuristic and Dijkstra baseline search; mathematical cost equivalence test; SUMO microscopic car-following validation. | `tests/test_api.py`, `tests/test_prediction_routing.py`, `experiments/sumo_validation.py`, `experiments/partial_info.py`. | **[MATHEMATICAL PROOF & SIMULATION]** Cost difference: `0.000000 min` (exact cost match); A* expands 55-65% fewer nodes than Dijkstra. Partial info regret evaluated in seconds for $K \in \{5, 15, 40\}$. | BPR travel time function is macroscopic. Under oversaturation ($V/C > 1.0$), microscopic simulation exhibits boundary insertion delay (up to 84.9s) and unserved vehicle backlog (up to 125 veh). Isolated single-link simulation does NOT model network-wide spatial queue spillback into upstream junctions. |
| **Platform** | Full-stack FastAPI + SQLAlchemy 2.0 with Alembic migrations (16 tables), RBAC, persistent expiring sessions, rate limiting, and Docker Compose. | `tests/test_api.py`, `tests/test_hardening.py`, `ui_smoke.js` (61 of 61 passed). | **[SQLITE EXECUTION]** 16-table ER diagram in `ARCHITECTURE.md`, 15 dedicated UI pages verified in JSDOM virtual browser. | **UNPROVEN ON THIS MACHINE**: Automated tests ran against SQLite 3 (`PRAGMA foreign_keys = ON`). Execution of PostgreSQL 16 via `docker compose up` was blocked because the Docker Desktop daemon service is stopped on this Windows host. |

---

## 2. Status of Unproven Items Under The Evidence Rule

1. **Live TomTom Data & Polling:**
   - `TOMTOM_API_KEY` was not configured in the host environment (`KEY_PRESENT: False`).
   - In adherence to **The Evidence Rule**, no live readings, counts, or timestamps were fabricated. Running `experiments/test_live_tomtom.py` verified the presence of the environment variable, safely aborted upon detecting its absence, and documented the exact steps to enable live mode once a key is provided.
   - The platform safely fell back to the simulated diurnal profile and clearly displayed `SIMULATED` traffic mode in all dashboards.

2. **Docker Compose & PostgreSQL Execution:**
   - Executing `docker compose up` failed with `open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified` because the Docker Desktop daemon service was not running on the Windows host.
   - Consequently, running the test suite directly against PostgreSQL remains **unproven on this machine**.
   - All 29 automated backend tests and 61 UI smoke checks executed and passed against SQLite 3 with foreign key constraints strictly enforced (`PRAGMA foreign_keys = ON`).

3. **SUMO Network-Wide Spatial Queue Spillback:**
   - The SUMO-compatible Krauss / IDM microscopic simulation validates single-link car-following dynamics on Anna Nagar Edge #0 ($L = 0.44$ km).
   - For oversaturated demand ($V/C > 1.0$), the simulation accurately models upstream boundary insertion delay (0.3s at $V/C=0.2$ to 84.9s at $V/C=1.8$) and accumulating unserved backlog (up to 125 vehicles).
   - **Crucial Clarification**: Because this is an isolated single-corridor simulation, it does **NOT** simulate multi-junction spatial queue spillback into upstream intersections. Latency is driven by headway acceptance delays at the link entrance and intra-link car-following deceleration, not network-wide junction gridlock.

4. **Partial-Information Fixed-Quota Comparisons:**
   - In `experiments/partial_info.py`, `central` and `random` monitoring strategies were evaluated at strictly identical network monitoring quotas ($K \in \{5, 15, 40\}$) across 150 trials, measuring regret in seconds.
   - The `on_route` strategy was **dropped** from fixed-quota comparisons because querying roads along specific trips requires $K$ queries per OD journey rather than a fixed global network budget, making direct quota-equivalence comparisons scientifically invalid.

---

## 3. Parametric Assumptions

1. **Emergency Queue Bypass Factors:**
   - Critical: $b = 0.50$ (assumes siren and lights allow bypassing 50% of the standing queue on congested links).
   - Urgent: $b = 0.25$ (assumes 25% queue clearance).
   - Routine: $b = 0.00$ (no siren or priority; identical to standard car).
2. **Public Transport Dwell Time:**
   - Stop dwell time is fixed at 0.50 minutes (30 seconds) per stop for boarding and alighting.
3. **Macroscopic Link Travel Time (BPR Formula):**
   - $t = t_0 \times (1.0 + 0.15 \times (V/C)^4)$. Standard transportation engineering values ($\alpha = 0.15, \beta = 4.0$).

---

## 4. Hardware, Network, and Geolocation Constraints

1. **TomTom Free-Tier Quota:**
   - Throttled to stay strictly under 2,500 non-tile requests per day across all endpoints.
2. **OpenStreetMap Nominatim Rate Limit:**
   - Place search strictly enforces 1 request per second max, includes identified user-agent header, and caches results to avoid spamming the public OSM geocoding servers.
3. **Geolocation Tracking:**
   - In live browser deployments, HTML5 `watchPosition` provides GPS coordinates. In automated tests and when geolocation permission is denied, movement along the recommended path is simulated via coordinate interpolation.
