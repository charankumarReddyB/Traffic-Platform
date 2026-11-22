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

## 2. Status of Unproven Items and Methodological Explanations Under The Evidence Rule

1. **Partial-Information Study Regret Values & Historical Transcription Discrepancies:**
   - **Root Cause of Historical Transcription Error**: In an earlier release of `reports.html`, the author manually updated the table rows to replace `on_route` with `central`. During this manual edit:
     - For `central-40`: The value $0.0538\text{ min} \times 60 = 3.23\text{ s}$ was mistakenly transcribed as `4.64 s` from an adjacent intermediate draft row, while retaining the true bootstrap benefit-retained percentage ($65.8\%$).
     - For `central-15`: The confidence interval `[13.0%, 77.7%]` was copied directly from the old `on_route, K=15` row instead of using the true `central-15` CI (`[0.8%, 20.4%]`).
     - Seconds conversions differed between rows because entries were manually typed rather than derived programmatically with $x \times 60$.
   - **Clean Rerun & Automated Generation**:
     - `backend/experiments/partial_info.py` was updated to explicitly seed NumPy's RNG (`--seed 42`), calculate `mean_regret_sec = round(mean_regret * 60, 2)` and bootstrap CI bounds in seconds directly in code, and output programmatically to `results.csv`.
     - Seed 42 run (150 trials) confirmed:
       - Baseline Car full info trip: 170.8 s, No live data regret: 7.2 s.
       - `all_roads` K=103, 5m: 0.01 s [0.00, 0.02], benefit: 99.9% [99.7%, 100.0%].
       - `central` K=40, 5m: 2.76 s [1.32, 4.61], benefit: 61.4% [31.4%, 80.3%].
       - `central` K=15, 5m: 6.59 s [3.52, 10.69], benefit: 7.9% [0.8%, 20.4%].
       - `central` K=5, 5m: 7.16 s [3.89, 11.20], benefit: 0.0% [0.0%, 0.0%].
       - `random` K=40, 5m: 4.35 s [1.98, 7.47], benefit: 39.2% [17.6%, 63.6%].
       - `random` K=15, 5m: 6.24 s [3.23, 9.88], benefit: 12.7% [1.5%, 29.9%].
       - `random` K=5, 5m: 6.87 s [3.94, 10.82], benefit: 3.9% [-0.6%, 12.6%].
   - **Quota Comparison Disclosure**: The `on_route` strategy is permanently excluded from fixed-quota comparisons because querying roads along specific trips requires $K$ queries per OD journey rather than a fixed global network budget, making direct quota-equivalence comparisons invalid.

2. **SUMO Single-Link Microscopic Validation & Oversaturation Dynamics:**
   - **Single-Link Check Scope Restriction**: The microscopic simulation is strictly executed on Edge #0 ($L = 0.436$ km, free-flow time = 0.654 min / 39.2 s, capacity = 1,000 veh/hr). Network-wide claims across multiple intersections are explicitly disclaimed.
   - **Delays Above Free Flow**:
     - At $V/C \le 1.0$, macroscopic BPR matches car-following simulation within 2.3% to 4.4% relative error (BPR delay = 0.0s to 5.9s vs Microscopic delay = 1.1s to 4.9s).
     - At $V/C > 1.0$, link travel times diverge because steady-state BPR extrapolates unbounded polynomial travel time ($t \to \infty$), whereas microscopic simulation reflects discrete vehicle entry headway acceptance, boundary queueing, and bottleneck accumulation.
   - **Boundary Insertion Delay vs Spatial Spillback**:
     - At $V/C = 1.8$, upstream boundary waiting reaches 84.9s with 125 unserved backlog vehicles.
     - Total microscopic time includes boundary insertion delay ($t_{\text{micro\_tot}} = t_{\text{traversal}} + t_{\text{insertion}}$), resulting in 16.8s traversal delay + 84.9s insertion delay = 101.7s total delay.
     - **Physical Spillback Clarification**: On an isolated single link, spatial queue spillback into upstream junctions does not physically exist. Latency represents link entry queueing and car-following deceleration, NOT 2D network junction blocking.

3. **FIFO Property (Arrive-Later-Never-Earlier) and Mathematical Boundaries:**
   - **Operational Guarantee**: Tested in `backend/tests/test_fifo_property.py`. Across all 103 road segments over a continuous 24-hour cycle at 1-minute time steps (148,320 point checks), departure at $t_2 > t_1$ satisfies arrival $t_2 + c(t_2) \ge t_1 + c(t_1)$ with **0 violations**. Monotonic arrival times are preserved along computed paths.
   - **Theoretical Non-FIFO Boundary Condition**:
     - The mathematical condition for First-In-First-Out (FIFO) routing is $\frac{dc(t)}{dt} \ge -1$.
     - When traffic clears rapidly, travel time decreases. If travel time falls faster than 1 second per second ($\frac{dc}{dt} < -1$), departing later results in arriving earlier.
     - In real-world urban roads, peak-to-off-peak clearance rates are smooth ($\approx 0.08$ min/min, well above $-1$).
     - However, with discrete tree-based machine learning models (such as un-interpolated Random Forest or Gradient Boosted Trees), split boundaries introduce discontinuous step drops. If a tree boundary drops travel time by $\Delta c > 0$ across a minute step $\Delta t$, and $\Delta c > \Delta t$, a theoretical violation exists at the exact split point. In our implementation, operational departure intervals ($\ge 1$ min) and continuous linear interpolation between forecast horizons restore strict monotonicity.

4. **Docker Compose & PostgreSQL Execution on Windows:**
   - **Status**: Docker Desktop on this Windows machine is currently stopped (`com.docker.service` status: `Stopped`).
   - Starting the Windows system service via PowerShell (`Start-Service com.docker.service`) requires elevated Administrator UAC permissions, which are restricted in this development shell session.
   - Consequently, running tests against a live PostgreSQL 16 container via `docker compose up` remains **unproven on this specific host**.
   - All 34 automated backend tests and 61 UI smoke checks + 34 interaction checks execute and pass against SQLite 3 with foreign key enforcement strictly enabled (`PRAGMA foreign_keys = ON`). All PostgreSQL Alembic migration scripts and Docker Compose configurations are verified syntactically.

5. **Role Page UI Interaction Testing:**
   - Full automated interaction tests are verified in `backend/tests/test_ui_interactions.js` using JSDOM across all 9 role and operational pages:
     1. `pending.html`: verifies token loading, auto-redirect logic, and logout button handlers.
     2. `bus_dashboard.html`: verifies route selection, delay calculation trigger, and schedule change proposal submission with JWT auth headers.
     3. `ambulance_dashboard.html`: verifies hospital selection, severity profile radio buttons (Critical/Urgent/Routine), start/complete trip actions, and HTML5 GPS telemetry mocking.
     4. `admin_dashboard.html`: verifies audit log rendering, user approval/suspension button interactions, and system reset controls.
     5. `route_compare.html`: verifies origin/destination selection, dynamic route calculation, and multi-criteria comparison metrics.
     6. `traffic_prediction.html`: verifies future departure time input, model forecast execution, and congestion chart population.
     7. `transit_planning.html`: verifies route modification simulator, headway input, and fleet sufficiency calculation.
     8. `scenarios.html`: verifies scenario preset triggers (A: Congestion, B: Ambulance, C: Bus, D: Before/After) and playback controls.
     9. `index.html`: verifies Nominatim geocoding place search button, 1-req/sec rate limiting, and search result selection.
   - Result: **All 34 of 34 interaction assertions passed**.

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
