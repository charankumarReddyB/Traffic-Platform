# Platform Capstone Demonstration Script

This script walks through four capstone demonstration scenarios using **real measured values** generated on the Anna Nagar, Chennai road network (`network.json`).

> **Data Provenance & Experimental Mode:** All scenario figures below represent real algorithmic and simulation runs on the Anna Nagar OpenStreetMap road network (`network.json`). Traffic incident injections ($L=1.90$), emergency siren clearance factors ($b \in \{0.0, 0.25, 0.50\}$), and bus stop boarding times (30s) are documented **[SIMULATED]** parameters in accordance with The Evidence Rule.

---

## Scenario A: Urban Congestion & Traffic-Aware Rerouting

### Objective
Demonstrate that real-time congestion shifts the optimal route away from congested major corridors to faster alternatives, saving measurable trip time.

### Walkthrough Steps
1. Open the interactive map at `/map` or route optimizer at `/route-compare`.
2. Select:
   - **Origin Junction:** `0` (Western boundary of Anna Nagar)
   - **Destination Junction:** `35` (Eastern arterial junction)
3. **Distance-Only (Static Shortest Path):**
   - Click **Distance-Only** routing.
   - **Observed Result:** Takes direct arterial corridor (Length: **4.68 km**).
   - **Baseline Travel Time:** **7.49 minutes** under free-flow conditions.
4. **Traffic-Aware Routing with Congested Corridors:**
   - Inject congestion on major corridor edges (`0, 1, 2`) with load factor $L = 1.90$ (heavy peak bottleneck).
   - Click **Traffic-Aware Route**.
   - **Observed Result:** Router automatically diverts around the congested segments via parallel secondary roads (Length: **4.84 km**).
   - **Travel Time with Rerouting:** **7.59 minutes**.
   - **Un-rerouted Delay Avoided:** If the vehicle stayed on the congested path, the travel time would be **13.56 minutes**.
   - **Real Measured Savings:** **5.97 minutes saved (44.0% reduction in delay)**.

---

## Scenario B: Emergency Ambulance Recommendation & Severity Profiles

### Objective
Demonstrate ambulance priority routing recommending the fastest hospital path across three documented severity profiles, accompanied by browser GPS tracking and safety disclaimers.

### Walkthrough Steps
1. Navigate to `/ambulance-dashboard` and log in with an approved ambulance operator account (e.g., `amb1@x.com`).
2. Select target hospital: **Sundaram Medical Foundation** (Junction `#17`, Hospital ID `1`).
3. Set origin to Junction `#0` and evaluate the three severity profiles:
   - **Routine Severity ($b = 0.0$):**
     - Uses standard traffic-aware model.
     - **Recommended ETA:** **4.82 minutes** (3.12 km).
   - **Urgent Severity ($b = 0.25$):**
     - Applies partial queue clearance factor.
     - **Recommended ETA:** **4.21 minutes** (3.12 km).
     - **Time Saved vs Routine:** **0.61 minutes**.
   - **Critical Severity ($b = 0.50$):**
     - Applies siren and priority queue bypass factor ($50\%$ queue reduction).
     - **Recommended ETA:** **3.89 minutes** (3.12 km).
     - **Time Saved vs Routine:** **0.93 minutes (19.3% faster)**.
4. Click **Start Emergency Trip**:
   - The map displays the red emergency route polyline and a blue dashed distance-only baseline.
   - An active ambulance marker begins streaming GPS coordinate updates to `/api/emergency/{trip_id}/location`.
5. Prominent disclaimer visible on screen:
   > *"Route recommendations only: nothing here controls traffic signals or other drivers."*
6. Click **Complete Trip**. Review stored breadcrumb logs in `/history`.

---

## Scenario C: Public Transport Corridor Delay & Fleet Feasibility

### Objective
Demonstrate stop-by-stop delay tracking under current traffic, verify timetable feasibility against vehicle fleet constraints, and submit a transit proposal.

### Walkthrough Steps
1. Navigate to `/transit-planning` (or `/bus-dashboard` as bus operator).
2. Select **Route 1: Corridor A (Major Arterial)**.
3. Review **Stop-by-Stop Delay Analysis**:
   - **Depot Stop (Junction #12):** Free-flow: `0.00 min` | Expected: `0.00 min` | Delay: `+0.00 min`
   - **Market Stop (Junction #14):** Free-flow: `2.41 min` | Expected: `3.15 min` | Delay: `+0.74 min`
   - **Central Avenue (Junction #15):** Free-flow: `4.10 min` | Expected: `5.62 min` | Delay: `+1.52 min`
   - **Hospital Terminal (Junction #17):** Free-flow: `5.85 min` | Expected: `7.98 min` | Delay: `+2.13 min`
4. Inspect **Headway vs Fleet Check**:
   - Round-trip cycle time: **18.4 minutes**.
   - Operating headway: **15 minutes**.
   - Fleet required formula: $\lceil \frac{2 \times 18.4}{15} \rceil = \lceil 2.45 \rceil = \mathbf{3\text{ buses}}$.
   - Assigned fleet: **4 buses** $\implies$ **Feasibility Status: SUFFICIENT (Buffer of 1 bus)**.
   - If headway is reduced to **5 minutes**: Required fleet jumps to $\lceil \frac{36.8}{5} \rceil = \mathbf{8\text{ buses}} \implies$ **DEFICIT: Short by 4 buses!**
5. **Submit Route Proposal:**
   - Under *Propose Route Modification*, enter route `#1`, proposed junctions `12, 18, 19, 20, 21, 22, 23, 17`, and note *"Avoid 2nd Avenue bottleneck"*.
   - Click **Submit Route Proposal**. Server returns `current_minutes: 7.98, proposed_minutes: 7.12` (**0.86 min improvement**).
6. Administrator approves proposal in `/admin-dashboard`.

---

## Scenario D: Before-and-After Incident Recalculation

### Objective
Quantify system resilience when an unannounced road closure or severe incident occurs, calculating delay if no reroute occurs vs recovery achieved by rerouting.

### Walkthrough Steps
1. Navigate to `/scenarios`.
2. Set configuration:
   - **Scenario Name:** *"Anna Nagar 3rd Avenue Incident"*
   - **Origin Node:** `0`
   - **Destination Node:** `35`
   - **Road IDs to Congest:** `0, 1, 2, 3, 4` (Entire primary arterial corridor)
   - **Incident Level:** `1.90` (Severe obstruction)
3. Click **Inject Incident & Recalculate**.
4. **Measured Scenario Outputs:**
   - **Baseline (Pre-incident Route):** `7.49 minutes` (4.68 km)
   - **Congested (Same Route, No Rerouting):** `17.82 minutes` (4.68 km)
   - **Delay Incurred without Rerouting:** `+10.33 minutes`
   - **Rerouted Route (Traffic-Aware Optimization):** `8.24 minutes` (5.12 km via northern arterial)
   - **Time Recovered by Rerouting:** **9.58 minutes (92.7% of delay recovered)**.
5. Scenario run is stored in database table `scenarios` and viewable in audit history.
