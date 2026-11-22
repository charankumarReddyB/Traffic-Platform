# Urban Traffic Platform — Backend Engine

This directory contains the FastAPI server, graph routing algorithms (A* and Dijkstra), machine learning models (Random Forest), PostgreSQL / SQLite persistence with Alembic migrations, and experimental validation modules.

---

## 1. Directory Structure

```
backend/
├── main.py                   # FastAPI REST API endpoints, routing & telemetry
├── database.py               # SQLAlchemy 2.0 engine, sessions & Alembic binding
├── models.py                 # SQLAlchemy relational ORM models (16 tables)
├── graph.py                  # A* & Dijkstra routing algorithms on OSM network
├── predictor.py              # Random Forest ML congestion predictor
├── traffic.py                # Live TomTom polling & quota manager (<2,500/day)
├── build_network.py          # OSMnx extractor for Anna Nagar, Chennai road network
├── network.json              # Real road network (73 junctions, 103 edges, 4 hospitals)
├── requirements.txt          # Python dependencies
├── alembic.ini               # Database migration configuration
├── Dockerfile                # Production container specification
├── alembic/                  # Version-controlled schema migrations
├── experiments/              # SUMO microscopic & partial-information studies
│   ├── sumo_validation.py    # Krauss/IDM car-following validation
│   ├── partial_info.py       # 150-trial edge sampling & regret study
│   └── test_live_tomtom.py   # Live TomTom ingestion harness
└── tests/                    # 29 automated pytest suites & UI smoke harness
    ├── test_api.py           # Core authentication, RBAC & API tests
    ├── test_prediction_routing.py # Route divergence & brute-force checks
    ├── ui_smoke.js           # Headless JSDOM tests for all 15 pages
    └── make_report.py        # Automated test report generator
```

---

## 2. Running Backend Directly

```bash
# Run with uvicorn
uvicorn main:app --host 127.0.0.1 --port 8000 --reload

# Run tests
pytest tests/ -v
```
