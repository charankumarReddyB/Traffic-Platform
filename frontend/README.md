# Urban Traffic Platform — Frontend Client

This directory contains the user interface components, interactive Leaflet maps, Chart.js telemetry dashboards, and client-side styling for the **AI-Powered Urban Traffic, Public Transport & Emergency Platform**.

---

## 1. Directory Structure

```
frontend/
├── landing.html              # Public landing page and architecture overview
├── login.html                # User and operator sign-in portal
├── register.html             # Account registration with role requests (bus/ambulance)
├── pending.html              # Pending administrative approval screen
├── index.html                # Unified operations console
├── bus_dashboard.html        # Bus operator dashboard (routes, stops, proposals)
├── ambulance_dashboard.html  # Emergency console (severity profiles, live GPS tracking)
├── admin_dashboard.html      # Administrative governance console (approvals, users, audit)
├── map.html                  # Interactive Leaflet traffic map of Anna Nagar, Chennai
├── route_compare.html        # Multi-strategy routing comparison (A* vs Dijkstra)
├── traffic_prediction.html   # AI diurnal congestion curves & ML accuracy metrics
├── transit_planning.html     # Bus transit schedules, headway checking & timetable
├── history.html              # Emergency trip & breadcrumb location history
├── scenarios.html            # Incident simulation & bottleneck recalculation
├── reports.html              # Evaluation reports & experimental study results
├── analysis.html             # Multi-chart visual analysis page
├── package.json              # Client testing dependencies (jsdom)
└── package-lock.json
```

---

## 2. Technology Stack

- **Map Rendering:** [Leaflet.js](https://leafletjs.com/) v1.9.4 with OpenStreetMap tile layers.
- **Data Visualization:** [Chart.js](https://www.chartjs.org/) for diurnal traffic curves and accuracy metrics.
- **Client Scripting:** Vanilla modern JavaScript (ES6+ async/await, Fetch API) with strict HTML escaping and zero heavy SPA frameworks.
- **Design System:** Responsive CSS3 variables with automatic light/dark mode preference detection.
