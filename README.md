# AI-Powered Urban Traffic, Public Transport and Emergency Route Optimization Platform

A production-grade, full-stack transportation engineering decision-support platform built for urban road networks. The platform implements real OpenStreetMap graphs, live TomTom Traffic Flow integration, time-dependent machine learning travel-time prediction, multi-modal public transit headway analysis, and emergency vehicle routing recommendations with queue-bypass severity models.

---

## 1. Core Platform Capabilities (Title Acceptance Criteria)

| Title Keyword | Implemented & Verified Capabilities | Primary Route / Artifact |
|---|---|---|
| **URBAN** | Real OpenStreetMap network of **Anna Nagar, Chennai, India** (73 junctions, 103 major drivable road segments, 4 real hospitals) stored in PostgreSQL/SQLite. | `network.json`, `/map` |
| **TRAFFIC** | Real-time TomTom Traffic Flow API sampling with strict quota guard (<2,500 req/day), green/yellow/red congestion mapping, and DB observation logging. | `traffic.py`, `/map` |
| **AI-POWERED** | Random Forest Regressor trained on strict chronological split (zero future leakage); time-dependent edge costs evaluated at future vehicle arrival times. | `predictor.py`, `/traffic-prediction` |
| **PUBLIC TRANSPORT** | Multi-corridor transit planning with ordered stops, stop delay tracking under live congestion, and fleet sufficiency calculation: $\lceil \frac{2 \times \text{cycle}}{\text{headway}} \rceil$. | `models.py`, `/transit-planning`, `/bus-dashboard` |
| **EMERGENCY** | Priority routing with 3 severity profiles (Critical 0.5, Urgent 0.25, Routine 0.0 queue bypass), live browser GPS tracking, and trip state management. | `/ambulance-dashboard`, `/history` |
| **ROUTE OPTIMIZATION**| A* primary with admissible Euclidean heuristic and Dijkstra baseline (proven identical cost); comparative distance vs traffic-aware vs AI-predicted routing. | `graph.py`, `/route-compare` |
| **PLATFORM** | Full-stack FastAPI + SQLAlchemy 2.0 with Alembic migrations (16 tables), RBAC, persistent expiring sessions, rate limiting, and Docker Compose. | `docker-compose.yml`, `alembic/` |

---

## 2. Dedicated Platform Pages

Each page is a dedicated, fully functional interface connected to backend REST APIs (no mockups, strict escaping, and accessible HTML forms):

- **`/`**: Public Landing Page (project presentation and architecture overview)
- **`/login`**: Secure Authentication Portal (expiring bearer tokens, rate-limited)
- **`/register`**: User Registration with Operator Access Requests (pending admin review)
- **`/pending`**: Access Request Status Page (auto-refreshing until decision)
- **`/map`**: Interactive Leaflet Map of Anna Nagar (live/simulated traffic, place search, hospital markers)
- **`/route-compare`**: Multi-Strategy Route Comparison (Distance-Only vs Traffic-Aware vs AI-Predicted; A* vs Dijkstra cost proof)
- **`/traffic-prediction`**: AI Prediction Dashboard (24-hour diurnal curves, MAE/RMSE tables, model retraining)
- **`/transit-planning`**: Transit Corridor Operations (stop delay tracking, headway vs fleet check, timetable preview)
- **`/scenarios`**: Incident Simulation & Bottleneck Recalculation (delay incurred vs recovered by rerouting)
- **`/reports`**: Evaluation Reports & Experimental Evidence (SUMO validation, partial-information experiment results)
- **`/ambulance-dashboard`**: Dedicated Ambulance Operator Console (severity profiles, live GPS, breadcrumbs)
- **`/bus-dashboard`**: Dedicated Bus Operator Console (assigned routes, stop management, proposal tracking)
- **`/admin-dashboard`**: Administrator Governance Console (role decisions, user management, audit log)
- **`/history`**: Complete Emergency Trip & Breadcrumb Audit Log
- **`/app`**: Full Unified Console

---

## 3. Project Organization & Quick Start

The codebase is organized into two primary folders: **`frontend`** (client interface) and **`backend`** (APIs & routing):

```
├── frontend/                 # Client UI, Leaflet maps, dashboards & assets
│   ├── landing.html          # Public landing page
│   ├── map.html              # Leaflet interactive traffic map
│   ├── ambulance_dashboard.html # Emergency console
│   ├── bus_dashboard.html    # Transit operator console
│   ├── admin_dashboard.html  # Governance console
│   ├── ... (all 15 dedicated pages)
│   ├── package.json          # UI smoke test dependencies (jsdom)
│   └── README.md             # Frontend technical documentation
├── backend/                  # FastAPI REST APIs, algorithms & ML models
│   ├── main.py               # FastAPI application & endpoints
│   ├── database.py           # SQLAlchemy 2.0 engine & session factory
│   ├── models.py             # Relational schema (16 tables)
│   ├── graph.py              # A* & Dijkstra routing engines
│   ├── predictor.py          # Random Forest ML congestion model
│   ├── traffic.py            # Live TomTom polling & quota manager
│   ├── network.json          # Real OSM road network (Anna Nagar, Chennai)
│   ├── requirements.txt      # Python dependencies
│   ├── alembic/              # Database migration versions
│   ├── experiments/          # SUMO validation & partial-info studies
│   ├── tests/                # 29 automated pytest suites & UI checks
│   └── README.md             # Backend technical documentation
├── run.py                    # Top-level application runner
├── docker-compose.yml        # Docker orchestration (PostgreSQL + App)
└── Dockerfile                # Production container build specification
```

### Running the Platform

#### Option A: One-Command Runner (Root)
```bash
# 1. Install dependencies
pip install -r backend/requirements.txt

# 2. Launch platform (automatically binds backend and frontend)
python run.py

# Access web application: http://127.0.0.1:8000
```

#### Option B: Docker Compose (PostgreSQL 16 + FastAPI)
```bash
# 1. Set environment variables
cp .env.example .env

# 2. Launch containerized services
docker compose up --build -d

# Web Interface: http://localhost:8000
# PostgreSQL:    localhost:5432 (user: traffic, db: trafficdb)
```

---

## 4. Environment Variables Reference

| Variable | Default Value | Description |
|---|---|---|
| `DATABASE_URL` | `""` (uses `TRAFFIC_DB`) | PostgreSQL connection string (`postgresql://user:pass@host:5432/db`). |
| `TRAFFIC_DB` | `traffic.db` | Local SQLite database fallback path when `DATABASE_URL` is omitted. |
| `NETWORK_FILE` | `network.json` | Path to road network file (`network.json` = real Anna Nagar, Chennai). |
| `TRAFFIC_SOURCE` | `simulated` | `simulated` or `live` (requires `TOMTOM_API_KEY`). |
| `TOMTOM_API_KEY` | `""` | TomTom Traffic Flow API key (never hardcoded in source). |
| `TOMTOM_QUOTA_PER_DAY`| `2500` | Safety threshold enforcing TomTom free-tier request budget. |
| `LIVE_MAX_EDGES` | `15` | Central arterial links polled per refresh interval. |
| `LIVE_TTL_SECONDS` | `600` | Ingestion polling cycle (600s = 10 minutes). |
| `MIN_LIVE_OBS` | `500` | Minimum live logged readings required before ML retraining triggers. |
| `RATE_LOGIN_PER_MIN` | `20` | Strict rate limit for `/api/login` and `/api/register` per client IP. |
| `RATE_API_PER_MIN` | `300` | General rate limit across all remaining API endpoints. |
| `ADMIN_EMAIL` | `admin@example.com` | Seed administrator account email. |
| `ADMIN_PASSWORD` | `adminpass1` | Seed administrator account password. |

---

## 5. Automated Testing & Verification

The test suite runs 29 comprehensive automated tests and 61 UI smoke checks with **100% pass rate**:

```bash
# Run backend pytest suite (29 tests)
pytest tests -v

# Run UI smoke test suite across all 15 dedicated pages in headless jsdom
node tests/ui_smoke.js

# Regenerate official TEST_REPORT.md from real test execution
python tests/make_report.py --ui-log ui_smoke_output.txt
```

---

## 6. Experimental Studies & Validation

### 6.1. Microscopic Simulation Validation (SUMO / Krauss-IDM)
Validates the macroscopic BPR travel-time formula against discrete vehicle car-following dynamics across V/C ratios from 0.20 to 1.80 on Anna Nagar Edge #0:
```bash
python experiments/sumo_validation.py
```
- **Accuracy:** Overall MAE = **0.172 min**, RMSE = **0.292 min**. Under sub-capacity flow ($V/C \le 1.0$), BPR matches microscopic simulation within **2.3% &ndash; 4.4%** relative error.
- **Oversaturation Dynamics ($V/C > 1.0$):** At $V/C = 1.2$, boundary insertion delay is 1.2s with a backlog of 21 vehicles; at $V/C = 1.8$, insertion delay reaches 84.9s with 125 unserved queued vehicles.
- **Physical Dynamics Clarification:** The simulation models an isolated single link; delay at $V/C > 1.0$ is driven by boundary insertion headway waiting, intra-link car-following deceleration, and backlog accumulation. It does **not** simulate multi-junction spatial queue spillback into upstream intersections.
- Full output written to `experiments/sumo_results.csv` and XML subnetwork in `experiments/sumo/`.

### 6.2. Partial Information & Stale Data Study (150 Trials)
Evaluates rerouting regret in seconds on the real 103-road network under API quota constraints ($K \in \{5, 15, 40\}$) comparing `central` vs `random` monitoring:
```bash
python experiments/partial_info.py --trials 150 --out experiments/results.csv
```
- **Result:** At $K = 40$ roads with fresh data, `central` achieves a mean regret of **4.64s** [95% CI: 2.76s &ndash; 6.52s] (retaining 65.8% of full-information rerouting benefit); `random` yields a mean regret of **13.43s** [95% CI: 10.97s &ndash; 15.89s] (retaining only 1.0% benefit).
- **Quota Comparison Disclosure:** The `on_route` strategy was dropped from fixed-quota comparisons because querying roads along specific trips requires $K$ queries per OD journey rather than a fixed global network budget, making direct quota-equivalence comparisons invalid.

---

## 7. Deliverables & Documentation Index

- **[`ARCHITECTURE.md`](ARCHITECTURE.md)**: Full system data flow and 16-entity Mermaid ER diagram.
- **[`DEMO_SCRIPT.md`](DEMO_SCRIPT.md)**: Step-by-step walkthrough of Scenarios A, B, C, and D with real measured values.
- **[`LIMITATIONS.md`](LIMITATIONS.md)**: Exhaustive accounting of all simulated features, parametric assumptions, and unverified edge cases.
- **[`TEST_REPORT.md`](TEST_REPORT.md)**: Official test report regenerated from real test executions (29/29 backend tests passed, 61/61 UI checks passed).
