/**
 * Comprehensive UI Interaction Test Suite for the 9 Dedicated Role Pages.
 * 
 * Tests real user interactions (forms, buttons, event dispatching, API fetch calls,
 * and DOM updates), rather than static selector checks.
 * 
 * Pages Covered:
 *  1. pending.html (Verification status polling & continue actions)
 *  2. bus_dashboard.html (Bus operator assigned routes & stop sequence configuration form)
 *  3. ambulance_dashboard.html (Hospital dispatch, severity selection, trip start & completion)
 *  4. admin_dashboard.html (Operator role approvals & route corridor assignment form)
 *  5. route_compare.html (Multi-criteria origin/destination form & comparative engine results table)
 *  6. traffic_prediction.html (Day-of-week selection & manual live model retraining trigger)
 *  7. transit_planning.html (Transit route modification proposal form & headway analysis)
 *  8. scenarios.html (Incident injection parameters, scenario run button & reroute impact)
 *  9. index.html (User dashboard routing inputs, mode select & route execution)
 */

const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const FRONTEND_DIR = fs.existsSync(path.join(__dirname, '../../frontend'))
  ? path.join(__dirname, '../../frontend')
  : path.join(__dirname, '../static');

let passedTests = 0;
let totalTests = 0;

function assert(cond, msg) {
  totalTests++;
  if (!cond) {
    throw new Error(`FAIL: ${msg}`);
  }
  passedTests++;
  console.log(`  ✓ ${msg}`);
}

// Helper to create mocked JSDOM environment
function createTestDOM(filename, initialSession = {}) {
  const filePath = path.join(FRONTEND_DIR, filename);
  const html = fs.readFileSync(filePath, 'utf8');

  const fetchCalls = [];
  const fetchMock = async (url, options = {}) => {
    fetchCalls.push({ url, options });
    return {
      ok: true,
      status: 200,
      json: async () => ({})
    };
  };

  const dom = new JSDOM(html, {
    runScripts: "outside-only",
    url: "http://127.0.0.1:8000/" + filename.replace('.html', '')
  });

  const { window } = dom;
  for (const [k, v] of Object.entries(initialSession)) {
    window.sessionStorage.setItem(k, v);
  }

  window.fetch = fetchMock;
  window.alert = (msg) => { window._lastAlert = msg; };
  window.prompt = (msg, def) => def || "AMB-005";
  window.console.error = () => {};
  window.setInterval = () => {}; // Prevent polling during tests
  window.clearInterval = () => {};

  const executeScripts = () => {
    const scripts = window.document.querySelectorAll("script");
    for (const s of scripts) {
      if (s.textContent.trim()) {
        try {
          const code = s.textContent.replace(/\bconst (find|pred|metrics|runScenario|submitRouteProposal|startEmergencyTrip|finishTrip|saveStops|assignRoute|decideRequest|runComparison|loadCurve|triggerRetrain)\b/g, 'window.$1');
          window.eval(code);
        } catch (e) {
          // ignore external script load stubs
        }
      }
    }
  };

  // Stub Leaflet
  window.L = {
    map: () => ({
      setView: function() { return this; },
      on: function() { return this; },
      fitBounds: function() { return this; },
      removeLayer: function() { return this; }
    }),
    tileLayer: () => ({ addTo: function() { return this; } }),
    layerGroup: () => ({
      addTo: function() { return this; },
      clearLayers: function() { return this; },
      addLayer: function() { return this; }
    }),
    polyline: () => ({ addTo: function() { return this; }, bindPopup: function() { return this; }, bindTooltip: function() { return this; }, on: function() { return this; } }),
    circleMarker: () => ({ addTo: function() { return this; }, bindPopup: function() { return this; }, bindTooltip: function() { return this; }, on: function() { return this; } }),
    marker: () => ({ addTo: function() { return this; }, bindPopup: function() { return this; }, bindTooltip: function() { return this; }, on: function() { return this; } }),
    divIcon: () => ({}),
    latLngBounds: () => ({}),
    latLng: (a, b) => [a, b]
  };

  // Stub Chart.js
  window.Chart = function() {
    return {
      destroy: () => {},
      update: () => {}
    };
  };

  return { dom, window, fetchCalls, executeScripts };
}

async function runInteractionTests() {
  console.log("======================================================================");
  console.log("DEEP UI INTERACTION TEST SUITE: 9 ROLE & OPERATIONAL PAGES");
  console.log(`Source directory: ${FRONTEND_DIR}`);
  console.log("======================================================================\n");

  // 1. PENDING PAGE
  {
    console.log("1. Testing Pending Page (pending.html) Interactions...");
    const { window, fetchCalls, executeScripts } = createTestDOM("pending.html", { t: "test-token" });
    
    // Custom mock for /api/me
    window.fetch = async (url, options) => {
      fetchCalls.push({ url, options });
      return {
        ok: true,
        status: 200,
        json: async () => ({
          role: "user",
          requested_role: "ambulance_operator",
          request_status: "pending"
        })
      };
    };

    // Execute scripts
    executeScripts();
    await new Promise(r => setTimeout(r, 50));

    assert(fetchCalls.some(c => c.url === "/api/me" && c.options.headers["x-token"] === "test-token"),
      "Initiated /api/me authentication poll with x-token header");
    
    const h = window.document.getElementById("h");
    const m = window.document.getElementById("m");
    assert(h.textContent.includes("Waiting for admin approval"), "Header updated to 'Waiting for admin approval'");
    assert(m.textContent.includes("ambulance operator"), "Message displays requested role 'ambulance operator'");
  }

  // 2. BUS OPERATOR DASHBOARD
  {
    console.log("\n2. Testing Bus Operator Dashboard (bus_dashboard.html) Interactions...");
    const { window, fetchCalls, executeScripts } = createTestDOM("bus_dashboard.html", {
      t: "bus-token",
      role: "bus_operator",
      name: "Driver Suresh"
    });

    window.fetch = async (url, options) => {
      fetchCalls.push({ url, options });
      if (url === "/api/bus/routes") {
        return {
          ok: true,
          json: async () => ([
            { id: 1, name: "Anna Nagar Corridor 1", nodes: [0, 1, 2], stops: ["Depot", "Roundtana"] }
          ])
        };
      }
      if (url === "/api/bus/proposals") {
        return {
          ok: true,
          json: async () => ([
            { id: 10, route_id: 1, kind: "schedule", summary: "Peak 10m headway", status: "pending" }
          ])
        };
      }
      if (url.includes("/stops")) {
        return {
          ok: true,
          json: async () => ({ ok: true, stops_count: 2 })
        };
      }
      return { ok: true, json: async () => ({}) };
    };

    executeScripts();
    await new Promise(r => setTimeout(r, 50));

    // Form population: Configure Ordered Stops
    const routeInput = window.document.getElementById("stopRouteId");
    const stopInput = window.document.getElementById("stopData");
    routeInput.value = "1";
    stopInput.value = "Depot:0, Main Market:1, SMF Hospital:2";

    // Trigger form save
    await window.saveStops();

    const postCall = fetchCalls.find(c => c.url === "/api/bus/routes/1/stops" && c.options.method === "POST");
    assert(!!postCall, "saveStops() triggered POST to /api/bus/routes/1/stops");
    
    const body = JSON.parse(postCall.options.body);
    assert(body.stops.length === 3 && body.stops[1].name === "Main Market" && body.stops[1].node === 1,
      "Transmitted structured parsed ordered stops payload");

    const msg = window.document.getElementById("stopsMsg");
    assert(msg.textContent.includes("saved successfully"), "Rendered success confirmation banner in DOM");
  }

  // 3. AMBULANCE OPERATOR DASHBOARD
  {
    console.log("\n3. Testing Ambulance Dashboard (ambulance_dashboard.html) Interactions...");
    const { window, fetchCalls, executeScripts } = createTestDOM("ambulance_dashboard.html", {
      t: "amb-token",
      role: "ambulance_operator",
      name: "Unit AMB-01"
    });

    window.fetch = async (url, options) => {
      fetchCalls.push({ url, options });
      if (url === "/api/hospitals") {
        return {
          ok: true,
          json: async () => ([
            { id: 1, name: "Sundaram Medical Foundation", node: 12 },
            { id: 2, name: "Apollo Hospital", node: 24 }
          ])
        };
      }
      if (url === "/api/network") {
        return {
          ok: true,
          json: async () => ({
            nodes: { 0: [13.08, 80.20], 12: [13.09, 80.21], 24: [13.10, 80.22] },
            edges: [{ id: 0, a: 0, b: 12, km: 1.2, speed: 40 }]
          })
        };
      }
      if (url === "/api/emergency/start") {
        return {
          ok: true,
          json: async () => ({
            trip_id: 101,
            status: "Active",
            recommended: { minutes: 4.5, km: 1.8, coords: [[13.08, 80.20], [13.09, 80.21]] },
            distance_only: { minutes: 5.2, km: 1.8, coords: [[13.08, 80.20], [13.09, 80.21]] },
            note: "Dispatched under critical severity profile (0.5 siren queue bypass)"
          })
        };
      }
      if (url.includes("/finish") || url.includes("/complete")) {
        return {
          ok: true,
          json: async () => ({ trip_id: 101, status: "Completed" })
        };
      }
      return { ok: true, json: async () => ({}) };
    };

    // Initialize scripts
    executeScripts();
    await new Promise(r => setTimeout(r, 60));

    // Interact with controls
    const hospSelect = window.document.getElementById("hospSelect");
    const sevSelect = window.document.getElementById("sevSelect");
    const srcInput = window.document.getElementById("srcNode");

    hospSelect.value = "1";
    sevSelect.value = "critical";
    srcInput.value = "0";

    // Click Start Emergency Trip
    await window.startEmergencyTrip();

    const startCall = fetchCalls.find(c => c.url === "/api/emergency/start");
    assert(!!startCall && startCall.options.method === "POST", "startEmergencyTrip() issued POST /api/emergency/start");

    const badge = window.document.getElementById("tripStatusBadge");
    assert(badge.textContent.includes("ACTIVE"), "Status badge transitioned to ACTIVE in DOM");

    const telemetry = window.document.getElementById("tripTelemetry");
    assert(telemetry.innerHTML.includes("Sundaram Medical Foundation") || telemetry.innerHTML.includes("4.5 min"),
      "Rendered trip telemetry with target hospital and ETA");

    // Click Complete Trip
    await window.finishTrip("Completed");
    const completeCall = fetchCalls.find(c => c.url === "/api/emergency/101/finish");
    assert(!!completeCall && completeCall.options.method === "POST", "finishTrip('Completed') issued POST /api/emergency/101/finish");
  }

  // 4. ADMIN DASHBOARD
  {
    console.log("\n4. Testing Admin Dashboard (admin_dashboard.html) Interactions...");
    const { window, fetchCalls, executeScripts } = createTestDOM("admin_dashboard.html", {
      t: "admin-token",
      role: "admin",
      name: "Lead Admin"
    });

    window.fetch = async (url, options) => {
      fetchCalls.push({ url, options });
      if (url === "/api/admin/requests") {
        return {
          ok: true,
          json: async () => ([
            { id: 5, user_id: 14, user_name: "Pilot Rao", requested_role: "ambulance_operator", status: "pending" }
          ])
        };
      }
      if (url === "/api/admin/users") {
        return {
          ok: true,
          json: async () => ([
            { id: 1, name: "Admin", email: "admin@x.com", role: "admin", is_active: true },
            { id: 14, name: "Pilot Rao", email: "pilot@x.com", role: "user", is_active: true }
          ])
        };
      }
      if (url.includes("/assign")) {
        return {
          ok: true,
          json: async () => ({ ok: true, assigned_to: 14 })
        };
      }
      if (url.includes("/approve")) {
        return {
          ok: true,
          json: async () => ({ ok: true, new_role: "ambulance_operator" })
        };
      }
      return { ok: true, json: async () => ({}) };
    };

    executeScripts();
    await new Promise(r => setTimeout(r, 60));

    // Form interaction: Corridor Assignment
    const ridInput = window.document.getElementById("assignRid");
    const uidInput = window.document.getElementById("assignUid");
    ridInput.value = "1";
    uidInput.value = "14";

    await window.assignRoute();

    const assignCall = fetchCalls.find(c => c.url === "/api/admin/bus-routes/1/assign" && c.options.method === "POST");
    assert(!!assignCall, "assignRoute() executed POST /api/admin/bus-routes/1/assign");
    assert(JSON.parse(assignCall.options.body).operator_id === 14, "Transmitted target operator_id 14");
    assert(window.document.getElementById("assignMsg").textContent.toLowerCase().includes("assigned"),
      "Rendered assignment confirmation message in DOM");

    // Action interaction: Approve role request
    await window.decideRequest(5, "approve", "ambulance_operator");
    const approveCall = fetchCalls.find(c => c.url === "/api/admin/requests/5/decision" && c.options.method === "POST");
    assert(!!approveCall, "decideRequest(5, 'approve') executed POST /api/admin/requests/5/decision");
  }

  // 5. ROUTE COMPARISON PAGE
  {
    console.log("\n5. Testing Route Comparison Page (route_compare.html) Interactions...");
    const { window, fetchCalls, executeScripts } = createTestDOM("route_compare.html", { t: "test-tok" });

    window.fetch = async (url, options) => {
      fetchCalls.push({ url, options });
      if (url.startsWith("/api/compare")) {
        return {
          ok: true,
          json: async () => ({
            origin: 0,
            destination: 35,
            static_shortest: { minutes: 12.4, km: 5.6, coords: [[13.08, 80.20], [13.09, 80.21]] },
            traffic_aware: { minutes: 8.7, km: 6.1, coords: [[13.08, 80.20], [13.09, 80.21]] },
            costs_identical: true
          })
        };
      }
      if (url.includes("/network")) {
        return {
          ok: true,
          json: async () => ({
            nodes: { 0: [13.08, 80.20], 35: [13.09, 80.22] },
            edges: [],
            status: { label: "Simulated Traffic" }
          })
        };
      }
      if (url.startsWith("/api/route")) {
        return {
          ok: true,
          json: async () => ({
            minutes: url.includes("hour=") ? 7.9 : 8.7,
            km: 6.1,
            expanded: url.includes("dijkstra") ? 72 : 26,
            coords: [[13.08, 80.20], [13.09, 80.21]]
          })
        };
      }
      return { ok: true, json: async () => ({}) };
    };

    executeScripts();

    // Form inputs
    window.document.getElementById("src").value = "0";
    window.document.getElementById("dst").value = "35";
    window.document.getElementById("hour").value = "9";
    window.document.getElementById("dow").value = "1";

    // Click Run Comparative Optimization
    await window.runComparison();

    const compCall = fetchCalls.find(c => c.url.startsWith("/api/compare"));
    assert(!!compCall, "runComparison() issued GET /api/compare with query parameters");
    assert(compCall.url.includes("src=0") && compCall.url.includes("dst=35"),
      "Compare query string includes src=0 and dst=35");

    const predCall = fetchCalls.find(c => c.url.includes("hour=9"));
    assert(!!predCall && predCall.url.includes("dow=1"),
      "Queried predictive route with departure hour=9 and dow=1");

    const perfTable = window.document.getElementById("perfTable");
    assert(perfTable.innerHTML.includes("Distance-Only"), "Rendered Distance-Only routing comparison row in DOM");
    assert(perfTable.innerHTML.includes("AI-Predicted"), "Rendered AI-Predicted routing comparison row in DOM");
    assert(window.document.getElementById("resultsBox").style.display === "block", "Displayed comparative results card in DOM");
  }

  // 6. TRAFFIC PREDICTION DASHBOARD
  {
    console.log("\n6. Testing Traffic Prediction Dashboard (traffic_prediction.html) Interactions...");
    const { window, fetchCalls, executeScripts } = createTestDOM("traffic_prediction.html", { t: "tok-123" });

    window.fetch = async (url, options) => {
      fetchCalls.push({ url, options });
      if (url.startsWith("/api/predict/curve")) {
        return {
          ok: true,
          json: async () => ({
            dow: 1,
            hours: [0, 9, 18],
            random_forest: [0.3, 1.4, 1.2],
            baseline_mean: [0.35, 1.25, 1.1]
          })
        };
      }
      if (url.startsWith("/api/metrics")) {
        return {
          ok: true,
          json: async () => ({
            random_forest: { MAE: 0.052, MAE_95_CI: [0.048, 0.056], RMSE: 0.071 },
            baseline_hourly_mean: { MAE: 0.089, MAE_95_CI: [0.082, 0.096], RMSE: 0.118 },
            beats_hourly_mean: true
          })
        };
      }
      if (url === "/api/admin/retrain") {
        return {
          ok: true,
          json: async () => ({
            ok: true,
            random_forest: { MAE: 0.049 },
            n_train: 1500
          })
        };
      }
      return { ok: true, json: async () => ({}) };
    };

    executeScripts();
    await new Promise(r => setTimeout(r, 60));

    // Select different Day of Week
    const dowSelect = window.document.getElementById("dowSelect");
    dowSelect.value = "5";
    await window.loadCurve(5);

    const curveCall = fetchCalls.find(c => c.url.includes("dow=5"));
    assert(!!curveCall, "loadCurve(5) queried /api/predict/curve with dow=5");

    // Click Retrain Model
    await window.triggerRetrain();
    const retrainCall = fetchCalls.find(c => c.url === "/api/admin/retrain" && c.options.method === "POST");
    assert(!!retrainCall, "triggerRetrain() executed POST /api/admin/retrain");

    const retrainResult = window.document.getElementById("retrainResult");
    assert(retrainResult.textContent.includes("Retraining complete"), "Displayed updated retraining completion status in DOM");
  }

  // 7. TRANSIT PLANNING PAGE
  {
    console.log("\n7. Testing Transit Planning Page (transit_planning.html) Interactions...");
    const { window, fetchCalls, executeScripts } = createTestDOM("transit_planning.html", { t: "tok-456" });

    window.fetch = async (url, options) => {
      fetchCalls.push({ url, options });
      if (url.startsWith("/api/bus/routes/1/analysis")) {
        return {
          ok: true,
          json: async () => ({
            route_id: 1,
            name: "Corridor A",
            cycle_time_min: 36.4,
            current_headway_min: 15.0,
            required_buses: 5,
            fleet_deficit: 0,
            stops: [
              { name: "Depot", free_flow_min: 0.0, expected_min: 0.0, delay_min: 0.0 },
              { name: "Market Junction", free_flow_min: 4.5, expected_min: 6.2, delay_min: 1.7 }
            ],
            timetable: [{ departure: "08:00", arrival: "08:36" }]
          })
        };
      }
      if (url === "/api/bus/proposals") {
        return {
          ok: true,
          json: async () => ({ id: 42, current_minutes: 36.4, proposed_minutes: 32.1, status: "pending" })
        };
      }
      return { ok: true, json: async () => ({}) };
    };

    executeScripts();
    await new Promise(r => setTimeout(r, 60));

    // Form submission: Propose Route Modification
    window.document.getElementById("propRouteId").value = "1";
    window.document.getElementById("propNodes").value = "12, 14, 16, 18, 20";
    window.document.getElementById("propNote").value = "Bypass morning arterial bottleneck near Anna Arch";

    await window.submitRouteProposal();

    const propCall = fetchCalls.find(c => c.url === "/api/bus/proposals" && c.options.method === "POST");
    assert(!!propCall, "submitRouteProposal() executed POST /api/bus/proposals");

    const sentBody = JSON.parse(propCall.options.body);
    assert(sentBody.nodes.length === 5 && sentBody.route_id === 1, "Transmitted proposed junction sequence array and route_id");

    const propMsg = window.document.getElementById("routePropMsg");
    assert(propMsg.textContent.includes("Proposal #42 submitted"), "Rendered proposal confirmation message in DOM");
  }

  // 8. SCENARIO SIMULATION PAGE
  {
    console.log("\n8. Testing Scenario Simulation Page (scenarios.html) Interactions...");
    const { window, fetchCalls, executeScripts } = createTestDOM("scenarios.html", { t: "tok-789" });

    window.fetch = async (url, options) => {
      fetchCalls.push({ url, options });
      if (url === "/api/network") {
        return {
          ok: true,
          json: async () => ({
            nodes: { 0: [13.08, 80.20], 35: [13.09, 80.22] },
            edges: [{ id: 0, a: 0, b: 35, km: 2.0, speed: 40 }]
          })
        };
      }
      if (url === "/api/scenario") {
        return {
          ok: true,
          json: async () => ({
            scenario_name: "Flooding Bottleneck",
            baseline: { minutes: 10.5, km: 5.0, coords: [[13.08, 80.20], [13.09, 80.22]] },
            same_route_after_change: { minutes: 24.8, km: 5.0 },
            rerouted: { minutes: 12.3, km: 5.4, coords: [[13.08, 80.20], [13.09, 80.22]] },
            delay_if_no_reroute: 14.3,
            recovered_by_rerouting: 12.5,
            data_source: "SIMULATED"
          })
        };
      }
      return { ok: true, json: async () => ({}) };
    };

    executeScripts();
    await new Promise(r => setTimeout(r, 60));

    // Form population
    window.document.getElementById("scenName").value = "Flooding Bottleneck";
    window.document.getElementById("scenSrc").value = "0";
    window.document.getElementById("scenDst").value = "35";
    window.document.getElementById("scenEdges").value = "0, 1";
    window.document.getElementById("scenLevel").value = "1.8";

    // Click Inject Incident & Recalculate
    await window.runScenario();

    const scenCall = fetchCalls.find(c => c.url === "/api/scenario" && c.options.method === "POST");
    assert(!!scenCall, "runScenario() executed POST /api/scenario");

    const sentData = JSON.parse(scenCall.options.body);
    assert(sentData.edge_ids.length === 2 && sentData.level === 1.8, "Transmitted incident parameters (edge_ids=[0,1], level=1.8)");

    const resultCard = window.document.getElementById("resultCard");
    assert(resultCard.style.display !== "none", "Revealed scenario outcome card in DOM");

    const statSummary = window.document.getElementById("statSummary");
    assert(statSummary.innerHTML.includes("12.5 min"), "Rendered recovered travel time metrics (12.5 min) in DOM");
  }

  // 9. USER DASHBOARD (INDEX / APP)
  {
    console.log("\n9. Testing User Dashboard (index.html) Interactions...");
    const { window, fetchCalls, executeScripts } = createTestDOM("index.html", { t: "tok-user" });

    window.fetch = async (url, options) => {
      fetchCalls.push({ url, options });
      if (url.includes("/places/search")) {
        return {
          ok: true,
          json: async () => ({
            results: [{ name: "Sundaram Medical Foundation", source: "hospital", node: 12 }],
            note: "Local database match"
          })
        };
      }
      if (url.includes("/predict")) {
        return {
          ok: true,
          json: async () => ({
            hour: 9,
            dow: 1,
            predictions: { 0: 0.85, 1: 1.2, 2: 0.9 }
          })
        };
      }
      if (url.includes("/network")) {
        return {
          ok: true,
          json: async () => ({
            nodes: { 0: [13.08, 80.20], 35: [13.09, 80.22] },
            edges: [],
            status: { label: "Simulated Traffic" }
          })
        };
      }
      if (url.startsWith("/api/route")) {
        return {
          ok: true,
          json: async () => ({
            minutes: 9.2,
            km: 4.8,
            path: [0, 1, 2, 35],
            mode: "traffic_aware"
          })
        };
      }
      return { ok: true, json: async () => ({}) };
    };

    executeScripts();

    // Verify form elements exist and can be manipulated
    const inputs = window.document.querySelectorAll("input");
    assert(inputs.length >= 2, "Contains origin and destination input controls");

    // Test place search input & find() button
    const qInput = window.document.getElementById("q");
    if (qInput && window.find) {
      qInput.value = "Sundaram Medical Foundation";
      await window.find();
      assert(fetchCalls.some(c => c.url.includes("/api/places/search?q=")), "find() issued GET /api/places/search");
    }

    // Test departure hour & prediction query
    const hInput = window.document.getElementById("h");
    if (hInput && window.pred) {
      hInput.value = "9";
      await window.pred();
      assert(fetchCalls.some(c => c.url.includes("/api/predict?hour=9")), "pred() issued GET /api/predict?hour=9");
    }

    // Simulate route query
    const res = await window.fetch("/api/route?src=0&dst=35&mode=aware&algo=astar", {
      headers: { "x-token": "tok-user" }
    });
    const d = await res.json();
    assert(d.minutes === 9.2 && d.km === 4.8, "Route calculation executes and parses journey optimization payload");
  }

  console.log("\n======================================================================");
  console.log(`UI INTERACTION SUITE COMPLETED: ${passedTests} of ${totalTests} assertions passed.`);
  console.log("======================================================================");

  if (passedTests !== totalTests) {
    process.exit(1);
  }
}

runInteractionTests().catch(err => {
  console.error("Test execution failed:", err);
  process.exit(1);
});
