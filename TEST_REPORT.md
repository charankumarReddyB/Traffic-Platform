# Test report

Generated 2026-11-22 16:28 UTC on Python 3.14.7 (Windows). All numbers below come from this run.

## Summary
- Backend tests: **34 of 34 passed**.
- UI smoke checks: **61 passed, 0 failed**.
- Route calculation time (A*, traffic-aware, 0 to 35 on the 60-road simulated grid): **0.11 ms** on average over 200 runs.
- Test Database Execution: **SQLite 3 (PRAGMA foreign_keys = ON)**. Note: PostgreSQL 16 was not executed locally because Docker Desktop daemon is not running on host.
- Live Traffic Data Mode: **BLOCKED BY THE EVIDENCE RULE** (TOMTOM_API_KEY environment variable was not set).

## Results by requirement
| Requirement | Evidence (data source) | Result | Limits of the evidence |
|---|---|---|---|
| Registration and login | 1 test(s), 3 UI check(s) | **PASS** |  |
| Correct dashboard by role | 0 test(s), 8 UI check(s) | **PASS (with limits)** | Checked in a simulated browser; the automatic redirect to /pending was not exercised. |
| Blocking unauthorized API requests | 3 test(s) | **PASS** |  |
| Users cannot change their own role | 2 test(s) | **PASS** |  |
| Admin approval of ambulance accounts | 3 test(s) | **PASS** |  |
| Route calculation on known networks | 2 test(s), 3 UI check(s) | **PASS (with limits)** | Anna Nagar network and 6x6 grid. Cost equivalence verified between A* and Dijkstra. |
| Time-dependent A* route divergence | 1 test(s) | **PASS (with limits)** | [SYNTHETIC] Verifies that predicted rush-hour traffic shifts route choice from direct corridor to bypass, with peak path strictly faster than off-peak path. |
| A* time-dependent vs Brute-force equivalence | 1 test(s) | **PASS (with limits)** | [SYNTHETIC] Exhaustive brute-force check on all simple paths on 5-node graph matches A* with time-dependent cost (< 1e-9 min diff). |
| Arrive-later-never-earlier (FIFO) property | 5 test(s) | **PASS (with limits)** | Verified across all 103 road segments over 24h at 1-min intervals (148,320 checks: 0 violations). Theoretical step-drops at un-interpolated tree boundaries documented in LIMITATIONS.md. |
| Recalculation after simulated congestion | 2 test(s), 2 UI check(s) | **PASS (with limits)** | [SIMULATED] Congestion penalty injected into edge cost. |
| Denied or unavailable GPS | 1 test(s), 1 UI check(s) | **PASS (with limits)** | Covers GPS outside the simulated area and a browser with no geolocation. A real browser permission-denied prompt was not tested. |
| Create, complete, cancel emergency trips | 3 test(s), 3 UI check(s) | **PASS** |  |
| Bus-route comparison and schedules | 3 test(s), 3 UI check(s) | **PASS (with limits)** | Default stops and schedules are placeholders until set. |
| Traffic prediction evaluation | 4 test(s), 2 UI check(s) | **PASS (with limits)** | [SYNTHETIC] Model trains on synthetic diurnal observations. Live TomTom key was absent, so live training verified on synthetic data labelled as live. |
| Missing and invalid input | 4 test(s) | **PASS** |  |
| Place search (hospitals, stops, addresses) | 2 test(s), 2 UI check(s) | **PASS (with limits)** | Address lookups used a FAKE geocoder; the real Nominatim service was never called. |
| Output escaping (stored XSS) | 0 test(s), 1 UI check(s) | **PASS (with limits)** | Checked in a simulated browser on the admin user list; other pages were reviewed by hand, not tested. |
| Rate limiting and security headers | 1 test(s) | **PASS (with limits)** | No CSP header; HTTPS is a deployment matter. |
| Live traffic fallback behaviour | 2 test(s) | **PASS (with limits)** | Uses a FAKE provider when real TOMTOM_API_KEY is not set in environment. |
| Experiment harness correctness | 2 test(s) | **PASS (with limits)** | [SIMULATED] Harness only; its results are simulated. |
| All 15 UI pages rendered and served | 0 test(s), 15 UI check(s) | **PASS (with limits)** | Verified in JSDOM headless virtual browser with Leaflet and Chart.js stubs. |

## Failures
- none


## Limitations & Items Not Covered
- **Database Engine Used in Tests**: Backend tests ran against SQLite with foreign keys enforced. PostgreSQL is provided via Docker Compose (`docker-compose.yml`) and Alembic migrations, but Docker Desktop daemon is not running on the local host.
- **TomTom Live API**: Not queried during test runs because `TOMTOM_API_KEY` was absent from the host environment. Handled safely via simulated fallback.
- **Data Provenance**: Traffic speed observations and diurnal profiles are **SYNTHETIC/SIMULATED**; no claims of real-world TomTom measurement are made without an active API key.
- **Microscopic Simulation Dynamics**: SUMO-compatible Krauss/IDM microscopic simulation models single-link car-following and link-entry queueing. Oversaturation (V/C > 1.0) produces boundary insertion delay and accumulating unserved backlog, but does not simulate network-wide spatial queue spillback into upstream junctions.
- **UI Checks Scope**: All 15 dedicated pages were verified in a headless JSDOM environment; Leaflet map tiles, GPS geolocation prompts, and Chart.js canvas rendering are stubbed.
