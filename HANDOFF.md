# Handoff: Team 10 Traffic Decision-Support Platform

## Run it
1. `pip install -r requirements.txt`
2. `ADMIN_EMAIL=you@x.com ADMIN_PASSWORD=long-random uvicorn main:app --reload` (if you skip the variables, a random admin password is printed once on first run)
3. Open http://127.0.0.1:8000 (landing) then `/app`. Delete `traffic.db` after pulling schema changes (the bus_stops table changed).
Tests: `python -m pytest tests` (27 backend). UI check: start the server, `npm i jsdom`, run `node tests/ui_smoke.js` (33 checks, map/chart libraries stubbed). Report: `python tests/make_report.py`.

## File map
- `main.py` (~650 lines): all backend. Sections: graph + live-traffic layer, routing (A*/Dijkstra), SQLite + auth, bus routes/stops/schedules, emergency trips, role requests, place search, retraining, rate limiting.
- `static/`: `landing.html`, `index.html` (dashboard: map, all role tools), `pending.html`, `history.html`, `analysis.html` (charts).
- `build_network.py`: exports a real OpenStreetMap road network to `network.json` (never run here: no internet).
- `experiments/partial_info.py`: routing-loss study with partial/stale live data (simulated results only).
- `tests/`: backend tests, `ui_smoke.js`, `make_report.py`. `TEST_REPORT.md` is generated output.

## State
Works and tested: login/register, 4 roles with server-side checks, admin approval of operator requests, route compare, scenarios, ambulance trips with severity and history, bus stops/schedules/proposals, prediction + charts, place search (local), rate limiting, output escaping.
Written but NEVER run against the real services: TomTom live traffic (`TRAFFIC_SOURCE=live`), OSM export, Nominatim address search, Docker build.
Everything runs on SIMULATED traffic unless live mode is on. Keep that labelling.

## To do (priority order)
1. Open every page in a real browser and fix layout/behaviour bugs (only a stubbed browser was used).
2. Run `build_network.py` for a small real area, then live mode with a TomTom key. Check the TomTom URL and field names against its docs; free quota is 2,500 non-tile requests/day shared across products (defaults of 15 roads / 10 min can use about 2,160/day).
3. Separate pages for route comparison, scenario simulation, bus planning and an interactive map (currently buttons on the dashboard). Use real map clicks and replace `prompt()` dialogs with forms.
4. Real GPS: `watchPosition` updates during a trip (only the start point uses GPS now; movement is simulated).
5. PostgreSQL: replace the `sqlite3` calls in `main.py` (placeholders `?`, `executescript`, `PRAGMA table_info`, `INSERT OR REPLACE/IGNORE`, `lastrowid`, `rowcount`, `IntegrityError`). Move to SQLAlchemy + migrations. Optional: React frontend.
6. Production hardening: persistent sessions (tokens are in memory and lost on restart; the rate limiter is per process), password reset, CSP + HTTPS, secrets management.
7. Retrain the model on logged live readings (`/api/admin/retrain` exists; needs weeks of data).
8. Research: run the experiment on the real network, validate travel times against SUMO, do a targeted literature search before claiming novelty, then write the report and slides.

## Gotchas
- Importing `main` trains the Random Forest (a few seconds; slower on big networks, so keep the area small).
- Tests share one SQLite file across test modules; use unique emails/codes in new tests.
- Ambulance "bypass" factors (0.5/0.25/0) and bus dwell/layover values are assumptions, shown in the UI. Do not present them as measured.
- Ambulance trips only RECOMMEND routes; nothing controls signals.

## Starter prompt for the next AI tool
"This is a FastAPI + SQLite + vanilla-JS Leaflet app for a software-engineering capstone (see HANDOFF.md and README.md). Run the tests first and confirm they pass. Then work through the To-do list in order, one item at a time, adding or updating tests for each change, never removing the SIMULATED/LIVE labelling, and never claiming a result that was not produced by a test or experiment."
