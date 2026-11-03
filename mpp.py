"""Metropolitní plán Praha: development areas from IPR Praha open data, plus PID metro stations.

Licences: IPR data CC BY ("datový podklad © IPR Praha"); PID stop data CC BY (ROPID).
"""
import hashlib
import json
from datetime import datetime
from pathlib import Path

import requests

CACHE = Path(__file__).with_name("cache")  # last good answer of every request, used if a service is down

BASE = "https://mp.iprpraha.cz/arcgis/rest/services/Hosted"
AREAS_URL = f"{BASE}/MPP_CUR_MPP_400_POTENCIAL_P/FeatureServer/0"  # transformační a rozvojové plochy
LOCALITIES_URL = f"{BASE}/MPP_CUR_MPP_300_LOKALITY_P/FeatureServer/0"  # lokality (neighbourhood names)
PARKS_URL = f"{BASE}/MPP_CUR_MPP_100_PARKY_P/FeatureServer/0"  # městské parky
WATER_URL = f"{BASE}/URK_CUR_URK_SS_VODASPOJITA_P/FeatureServer/0"  # voda spojitá: river, ponds, lakes
TRANSPORT_LINES_URL = f"{BASE}/MPP_CUR_MPP_STAV_600_DI_TRASY_L/FeatureServer/0"  # existing transport lines
TRANSPORT_POINTS_URL = f"{BASE}/MPP_CUR_MPP_STAV_600_DI_ZARIZENI_B/FeatureServer/0"  # existing transport points
PLANNED_LINES_URL = f"{BASE}/MPP_CUR_MPP_600_DI_TRASY_L/FeatureServer/0"  # planned transport lines
METRO = 621  # 'kapitola' code of the metro in the transport layers
PID_STOPS_URL = "https://data.pid.cz/stops/json/stops.json"  # all PID stops with names and lines
PID_GTFS_URL = "https://data.pid.cz/PID_GTFS.zip"  # PID timetables incl. the path of every route
PRAGUE_BBOX = (14.22, 49.94, 14.71, 50.18)  # lon/lat box around Prague, to clip regional bus routes

WGS84 = 4326  # lat/lon for web maps
SJTSK = 5514  # Czech national grid, in metres: use it to measure areas


def _get(url, **params):
    key = hashlib.sha1(json.dumps([url, sorted(params.items())], default=str).encode()).hexdigest()
    cached = CACHE / f"{key}.json"
    try:
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise RuntimeError(f"{url}: {data['error'].get('message')}")
    except (requests.RequestException, RuntimeError, ValueError) as err:
        if not cached.exists():
            raise
        saved = datetime.fromtimestamp(cached.stat().st_mtime).strftime("%d. %m. %Y %H:%M")
        print(f"warning: {err} - using cached copy from {saved}")
        return json.loads(cached.read_text(encoding="utf-8"))
    CACHE.mkdir(exist_ok=True)
    cached.write_text(json.dumps(data), encoding="utf-8")
    return data


def _query(layer_url, **params):
    return _get(f"{layer_url}/query", **{"f": "json", **params})


def _domains(layer_url):
    """Code -> label lookups (e.g. stabilita 3 -> 'rozvojová'), read from the layer itself."""
    meta = _get(layer_url, f="json")
    return {
        field["name"]: {cv["code"]: cv["name"] for cv in field["domain"]["codedValues"]}
        for field in meta["fields"]
        if field.get("domain") and field["domain"].get("codedValues")
    }


def _ring_area(ring):
    # Shoelace formula; signed, so holes (opposite winding) subtract themselves.
    return sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(ring, ring[1:])) / 2


def _areas_m2():
    """True area of every development area, measured in S-JTSK (web-map areas are stretched ~2.4x)."""
    data = _query(AREAS_URL, where="1=1", outFields="objectid", returnGeometry="true", outSR=SJTSK)
    return {
        f["attributes"]["objectid"]: abs(sum(_ring_area(r) for r in f["geometry"]["rings"]))
        for f in data["features"]
    }


def _locality_names():
    data = _query(LOCALITIES_URL, where="1=1", outFields="lokalita,nazev", returnGeometry="false")
    return {f["attributes"]["lokalita"]: f["attributes"]["nazev"] for f in data["features"]}


def load_areas():
    """All transformation and development areas as GeoJSON, with readable attributes."""
    geojson = _query(AREAS_URL, where="1=1", outFields="*", outSR=WGS84, geometryPrecision=5, f="geojson")
    domains = _domains(AREAS_URL)
    areas = _areas_m2()
    names = _locality_names()

    for feature in geojson["features"]:
        p = feature["properties"]
        p["area_code"] = f"{p['kapitola']}/{p['lokalita']}/{p['id']}"
        p["locality_name"] = names.get(p["lokalita"], "")
        p["area_m2"] = round(areas.get(p["objectid"], 0))
        for field in ("stabilita", "vyuziti", "mira_vyuziti", "struktura"):
            p[f"{field}_txt"] = domains.get(field, {}).get(p[field], "")
    return geojson


def load_localities():
    """Neighbourhood shapes (lokality) as GeoJSON; together they draw the outline of Prague."""
    return _query(LOCALITIES_URL, where="1=1", outFields="lokalita,nazev", outSR=WGS84, geometryPrecision=5, maxAllowableOffset=0.00001, f="geojson")


def load_water():
    """All water surfaces as GeoJSON (the Vltava is one continuous shape)."""
    return _query(WATER_URL, where="1=1", outFields="objectid", outSR=WGS84, geometryPrecision=5, maxAllowableOffset=0.00001, f="geojson")


def load_parks():
    """City parks as GeoJSON (name only), for the green layer under the development areas."""
    return _query(PARKS_URL, where="1=1", outFields="nazev", outSR=WGS84, geometryPrecision=5, maxAllowableOffset=0.00001, f="geojson")


def _pid_stations(kind):
    """One point per PID stop in Prague for a traffic type (metro, tram, bus): its platforms averaged,
    with name, lines and S-JTSK x/y."""
    stations = []
    for group in _get(PID_STOPS_URL)["stopGroups"]:
        if group.get("municipality") != "Praha":
            continue
        platforms = [s for s in group["stops"] if any(l.get("type") == kind for l in s.get("lines", []))]
        if not platforms:
            continue
        mean = lambda key: sum(s[key] for s in platforms) / len(platforms)
        lines = sorted({l["name"] for s in platforms for l in s["lines"] if l.get("type") == kind},
                       key=lambda n: (len(n), n))
        stations.append({"name": group["name"], "lines": lines, "lat": mean("lat"), "lon": mean("lon"),
                         "x": mean("jtskX"), "y": mean("jtskY")})
    return stations


def load_metro_stations():
    return _pid_stations("metro")


def load_trams():
    """Existing tram tracks (Metropolitní plán, kapitola 622) as GeoJSON, plus PID tram stops."""
    tracks = _query(TRANSPORT_LINES_URL, where="kapitola=622", outFields="objectid", outSR=WGS84,
                    geometryPrecision=5, maxAllowableOffset=0.00001, f="geojson")
    return {"tracks": tracks, "stops": _pid_stations("tram")}


def load_bus_stops():
    return _pid_stations("bus")


def _gtfs_zip(max_age_days=7):
    """PID GTFS zip, downloaded into the cache and refreshed weekly (kept if a refresh fails)."""
    path = CACHE / "PID_GTFS.zip"
    fresh = path.exists() and (datetime.now().timestamp() - path.stat().st_mtime) < max_age_days * 86400
    if not fresh:
        try:
            CACHE.mkdir(exist_ok=True)
            with requests.get(PID_GTFS_URL, stream=True, timeout=120) as r:
                r.raise_for_status()
                with open(path.with_suffix(".part"), "wb") as out:
                    for chunk in r.iter_content(1 << 20):
                        out.write(chunk)
            path.with_suffix(".part").replace(path)
        except requests.RequestException as err:
            if not path.exists():
                raise
            print(f"warning: GTFS refresh failed ({err}) - using the cached copy")
    return path


def load_bus_routes():
    """The bus network as one GeoJSON MultiLineString: every bus route's path from PID GTFS,
    overlapping stretches merged, clipped to Prague and simplified to ~2 m."""
    import csv
    import io
    import zipfile

    from shapely.geometry import LineString, box, mapping
    from shapely.ops import linemerge, unary_union

    def rows(z, name):
        return csv.DictReader(io.TextIOWrapper(z.open(name), encoding="utf-8-sig"))

    with zipfile.ZipFile(_gtfs_zip()) as z:
        bus_routes = {r["route_id"] for r in rows(z, "routes.txt") if r["route_type"] == "3"}
        shape_ids = {t["shape_id"] for t in rows(z, "trips.txt") if t["route_id"] in bus_routes and t["shape_id"]}
        points = {}
        for p in rows(z, "shapes.txt"):
            if p["shape_id"] in shape_ids:
                points.setdefault(p["shape_id"], []).append(
                    (int(p["shape_pt_sequence"]), round(float(p["shape_pt_lon"]), 5), round(float(p["shape_pt_lat"]), 5)))

    # every consecutive point pair once, whichever direction or route it came from
    segments = set()
    for pts in points.values():
        pts.sort()
        for (_, x1, y1), (_, x2, y2) in zip(pts, pts[1:]):
            if (x1, y1) != (x2, y2):
                segments.add(tuple(sorted(((x1, y1), (x2, y2)))))
    network = linemerge([LineString(s) for s in segments])
    network = unary_union(network).intersection(box(*PRAGUE_BBOX)).simplify(0.00002)
    return {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": mapping(network)}]}


def load_metro():
    """Metro for the map: existing lines A/B/C and planned lines (stav 2) as GeoJSON, plus PID stations."""
    common = dict(outSR=WGS84, geometryPrecision=5, f="geojson")
    return {
        "lines": _query(TRANSPORT_LINES_URL, where=f"kapitola={METRO}", outFields="parametr", **common),
        "planned": _query(PLANNED_LINES_URL, where=f"kapitola={METRO} AND stav=2", outFields="nazev", **common),
        "stations": load_metro_stations(),
    }


if __name__ == "__main__":
    data = load_areas()
    print(f"{len(data['features'])} areas loaded")
    for f in data["features"]:
        p = f["properties"]
        if p["area_code"] == "414/267/5033":
            print({k: p[k] for k in ("area_code", "locality_name", "stabilita_txt", "vyuziti_txt",
                                     "struktura_txt", "z_max", "z_z", "v_z", "area_m2")})
