"""Screening facts for each area: metro access and flood risk.

Everything is measured in S-JTSK (metres), using the IPR open data loaded by mpp.py.
"""
from shapely.geometry import Point, shape
from shapely.ops import unary_union
from shapely.strtree import STRtree

from mpp import AREAS_URL, METRO, PLANNED_LINES_URL, SJTSK, _query, load_metro_stations

FLOOD_URL = "https://mp.iprpraha.cz/arcgis/rest/services/Hosted/MPP_CUR_MPP_700_TI_ZAPLAVUZ_P/FeatureServer/0"
PRICE_MAP_URL = "https://mp.iprpraha.cz/arcgis/rest/services/Hosted/SED_CUR_SED_CENOVAMAPA_P/FeatureServer/0"
PRICE_NEARBY_M = 500  # look this far around an area that has no priced land inside it
PAGE = 2000  # server's maxRecordCount


def _shapes(url, where, out_fields="objectid"):
    """All features in S-JTSK as (properties, shapely geometry), paging past the server's record limit."""
    params = dict(where=where, outFields=out_fields, outSR=SJTSK, f="geojson")
    data = _query(url, **params)
    features = data["features"]
    while data.get("exceededTransferLimit") or data.get("properties", {}).get("exceededTransferLimit"):
        data = _query(url, **params, resultOffset=len(features), resultRecordCount=PAGE, orderByFields="objectid")
        if not data["features"]:
            break
        features += data["features"]
    return [(f["properties"], shape(f["geometry"])) for f in features if f["geometry"]]


def _weighted_price(poly, zones, tree):
    """Area-weighted price of the priced zones overlapping poly, or None."""
    total = weight = 0
    for i in tree.query(poly, predicate="intersects"):
        price, zone = zones[i]
        w = poly.intersection(zone).area
        total, weight = total + price * w, weight + w
    return round(total / weight) if weight else None


def add_screening(areas):
    """Adds metro_name, metro_line, metro_m, metro_d_m, flood_pct, price and price_src to every area.

    price comes from the official price map (Kč/m²): priced zones inside the area if there are any
    (price_src "plocha"), otherwise priced zones within PRICE_NEARBY_M (price_src "okolí").
    """
    polygons = {p["objectid"]: g for p, g in _shapes(AREAS_URL, "1=1")}

    try:
        stops = load_metro_stations()
        stop_tree = STRtree([Point(s["x"], s["y"]) for s in stops])
        line_d = unary_union([g for _, g in _shapes(PLANNED_LINES_URL, f"kapitola={METRO} AND stav=2")])
    except Exception as err:  # transport service down and nothing cached yet: skip metro distances
        print(f"warning: metro data unavailable ({err})")
        stops = None
    try:
        flood = unary_union([g for _, g in _shapes(FLOOD_URL, "1=1")]).buffer(0)
    except Exception as err:  # same: skip flood check rather than fail the whole map
        print(f"warning: flood data unavailable ({err})")
        flood = None
    # price "N" means the zone has no price set
    zones = [(int(p["cena"]), g.buffer(0)) for p, g in _shapes(PRICE_MAP_URL, "cena <> 'N'", "cena")
             if p["cena"].isdigit()]
    zone_tree = STRtree([g for _, g in zones])

    for feature in areas["features"]:
        p = feature["properties"]
        poly = polygons.get(p["objectid"])
        if poly is None:
            continue
        if stops:
            stop = stops[stop_tree.nearest(poly)]
            p["metro_m"] = round(poly.distance(Point(stop["x"], stop["y"])))
            p["metro_name"], p["metro_line"] = stop["name"], stop["lines"][0]
            p["metro_d_m"] = round(poly.distance(line_d))
        if flood is not None:
            p["flood_pct"] = round(100 * poly.intersection(flood).area / poly.area) if poly.area else 0
        p["price"], p["price_src"] = _weighted_price(poly, zones, zone_tree), "plocha"
        if p["price"] is None:
            p["price"], p["price_src"] = _weighted_price(poly.buffer(PRICE_NEARBY_M), zones, zone_tree), "okolí"
        if p["price"] is None:
            p["price_src"] = None
    return areas


if __name__ == "__main__":
    from mpp import load_areas

    data = add_screening(load_areas())
    for f in data["features"]:
        p = f["properties"]
        if p["area_code"] in ("414/267/5033", "414/267/5540"):
            print({k: p.get(k) for k in ("area_code", "area_m2", "metro_name", "metro_line", "metro_m",
                                         "metro_d_m", "flood_pct", "price", "price_src")})
    flooded = sum(1 for f in data["features"] if f["properties"].get("flood_pct", 0) > 0)
    print(f"areas touching a flood zone: {flooded} of {len(data['features'])}")
    srcs = [f["properties"].get("price_src") for f in data["features"]]
    print({s: srcs.count(s) for s in ("plocha", "okolí", None)})
    prices = sorted(f["properties"]["price"] for f in data["features"] if f["properties"].get("price"))
    print("price range:", prices[0], "-", prices[-1], "| median", prices[len(prices) // 2])
