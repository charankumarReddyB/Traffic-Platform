"""Export a REAL road network + hospitals from OpenStreetMap to network.json.
Area: Anna Nagar, Chennai, India (Target Area)
"""
import sys, json, os
import osmnx as ox

def build(place="Anna Nagar, Chennai, India", dist=1400, out_file="network.json"):
    print(f"[build_network] Building real OSM network for: {place} (radius={dist}m)...")
    # Coordinates for Anna Nagar, Chennai
    center_point = (13.088249, 80.2073398)
    
    # Custom filter for major drivable roads
    cf = '["highway"~"trunk|primary|secondary|tertiary"]'
    try:
        G = ox.graph_from_point(center_point, dist=dist, network_type="drive", custom_filter=cf)
    except Exception as e:
        print(f"[build_network] graph_from_point failed: {e}. Trying address lookup...")
        G = ox.graph_from_address(place, dist=dist, network_type="drive", custom_filter=cf)
    
    G = ox.truncate.largest_component(G, strongly=False)
    ids = {n: i for i, n in enumerate(G.nodes)}
    seen, edges = set(), []
    
    def spd(d):
        try:
            return float(str(d.get("maxspeed", "40")).split()[0].split(";")[0])
        except Exception:
            return 40.0
            
    for u, v, d in G.edges(data=True):
        k = frozenset((u, v))
        if u != v and k not in seen:
            seen.add(k)
            edges.append([ids[u], ids[v], round(d["length"] / 1000, 4), spd(d)])
            
    nodes = {ids[n]: [round(G.nodes[n]["y"], 6), round(G.nodes[n]["x"], 6)] for n in G.nodes}
    
    # Query real hospitals in this area
    hosp = []
    try:
        f = ox.features_from_point(center_point, tags={"amenity": "hospital"}, dist=dist + 500)
        for _, r in f.iterrows():
            name = str(r.get("name", "")).strip()
            if not name or name == "nan" or name == "None":
                continue
            geom = r.geometry
            c = geom.centroid if hasattr(geom, "centroid") else geom
            n = ox.distance.nearest_nodes(G, c.x, c.y)
            hosp.append([name, ids[n]])
    except Exception as ex:
        print("[build_network] Features query note:", ex)
    
    # Fallback to verified real hospitals in Anna Nagar if none found in narrow radius
    real_anna_nagar_hospitals = [
        ("Sundaram Medical Foundation (SMF)", 13.0838, 80.2104),
        ("MGM Healthcare / KHM Hospital", 13.0872, 80.2145),
        ("Billroth Hospitals (Shenoy Nagar)", 13.0784, 80.2241),
    ]
    if len(hosp) < 2:
        for name, h_lat, h_lon in real_anna_nagar_hospitals:
            n = ox.distance.nearest_nodes(G, h_lon, h_lat)
            if not any(h[0] == name for h in hosp):
                hosp.append([name, ids[n]])
    
    # Keep top 3-4 real hospitals
    hosp = hosp[:4]
    
    out_data = {
        "area": place,
        "center": list(center_point),
        "dist": dist,
        "nodes": nodes,
        "edges": edges,
        "hospitals": hosp
    }
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(out_data, f, indent=2)
    print(f"[build_network] SUCCESS: {len(nodes)} junctions, {len(edges)} roads, {len(hosp)} real hospitals -> {out_file}")
    return out_data

if __name__ == "__main__":
    place = sys.argv[1] if len(sys.argv) > 1 else "Anna Nagar, Chennai, India"
    dist = int(sys.argv[2]) if len(sys.argv) > 2 else 1200
    build(place, dist)
