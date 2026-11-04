"""Builds index.html: a minimal dark map of Prague's development areas with cadastral parcels.

No street base map: Prague is drawn from its own plan data (neighbourhoods, parks, areas).
Clicking an area opens a deal sheet (deal_popup.js) that also lists its parcels live from ČÚZK.
"""
import hashlib
import json
import re
from pathlib import Path

import folium

from mpp import (load_areas, load_bus_routes, load_bus_stops, load_localities, load_metro, load_motorways_rail,
                 load_parks, load_rivers, load_train_stations, load_trams, load_water)
from screening import add_screening

OUT = Path(__file__).with_name("index.html")  # index.html so GitHub Pages serves it at the site root
DEAL_JS = Path(__file__).with_name("deal_popup.js")
FILTER_JS = Path(__file__).with_name("price_filter.js")
SEARCH_JS = Path(__file__).with_name("search.js")
SKY_JS = Path(__file__).with_name("sky.js")
I18N_JS = Path(__file__).with_name("i18n.js")
LINES_JS = Path(__file__).with_name("lines.js")
ACRE_WEB_DIR = Path(__file__).resolve().parent.parent / "Baldwin Acre" / "web"  # the Baldwin Acre page (read-only model viewer), copied to acre/
SELECT_JS = Path(__file__).with_name("selection.js")
DRAWER_JS = Path(__file__).with_name("drawer.js")
LIGHTNING_JS = Path(__file__).with_name("lightning.js")
CLOUDS_JS = Path(__file__).with_name("clouds.js")
EXPORT_JS = Path(__file__).with_name("export.js")
ACRE_XLSX = Path(__file__).resolve().parent.parent / "Baldwin Acre" / "Baldwin Acre.xlsx"  # the appraisal model, in its own folder
# The model is built on this area, so for it the export hands out the filled model itself as a worked
# example (copied next to the page on every build, so it follows the model)
ACRE_EXAMPLE_AREA, ACRE_EXAMPLE = "414/267/5033", "baldwin-acre-seberov.xlsx"
# Baldwin Alexandria (the source-library chatbot) is kept in its own folder and published as part of this
# site: every build copies its page, library and worker code into alexandria/ here
ALEXANDRIA_DIR = Path(__file__).resolve().parent.parent / "Baldwin Alexandria"
ALEXANDRIA_FILES = ("index.html", "knowledge.md", "worker.js")


def acre_copy():
    """A fresh copy of the Acre model to read and publish. Windows' own CopyFile works even while the
    model is open in Excel (Python cannot open the locked file itself)."""
    import ctypes
    import shutil
    import tempfile

    dst = Path(tempfile.gettempdir()) / "baldwin-acre-build.xlsx"
    try:
        shutil.copyfile(ACRE_XLSX, dst)
    except PermissionError:
        if not ctypes.windll.kernel32.CopyFileW(str(ACRE_XLSX), str(dst), False):
            raise
    return dst


def acre_template():
    """The Baldwin Acre model as an empty template, so "Export to Baldwin Acre" can write a workbook with
    the same sheets and cells: labels, formulas, fonts, fills, borders, number formats, column widths and
    merged cells. No numbers of the model go into the page (inputs, sensitivity axes, stored results),
    except the year counters of the cash-flow timelines (0, 1, 2 …), which the formulas build on. Excel
    "What-If" data tables can't be written by the export library and are left out."""
    import openpyxl
    from openpyxl.worksheet.formula import ArrayFormula, DataTableFormula

    def rgb(color):
        return color.rgb if color is not None and isinstance(color.rgb, str) else None

    def timeline(ws):
        """Cells holding year counters: a 0 that the next cell counts on from (=D56+1), or a row of 0, 1, 2 …"""
        keep = set()
        for row in ws.iter_rows():
            ints = [c for c in row if isinstance(c.value, int) and not isinstance(c.value, bool)]
            if len(ints) >= 3 and [c.value for c in ints] == list(range(len(ints))):
                keep.update(c.coordinate for c in ints)
            for i, c in enumerate(row[:-1]):
                nxt = row[i + 1].value
                if c.value == 0 and isinstance(nxt, str) and nxt.replace("$", "").startswith(f"={c.coordinate}+"):
                    keep.add(c.coordinate)
        return keep

    from collections import Counter

    def row_heights(ws):
        """The sheet's usual row height once, and the rows that differ (titles, section headers)."""
        hs = {r: ws.row_dimensions[r].height for r in range(1, ws.max_row + 1) if ws.row_dimensions[r].height}
        if not hs:
            return {}
        usual = Counter(hs.values()).most_common(1)[0][0]
        return {"rowH": usual, "rows": {r: h for r, h in hs.items() if h != usual}}

    sheets = []
    for ws in openpyxl.load_workbook(acre_copy()).worksheets:
        if ws.max_row <= 1 and ws.max_column <= 1 and ws["A1"].value is None:
            continue  # an empty sheet
        keep, cells = timeline(ws), []
        # the sheet's own look (the dark background and the usual font) is stored once, not per cell
        looks = Counter((rgb(c.fill.fgColor) if c.fill is not None and c.fill.fill_type == "solid" else None,
                         c.font.name, c.font.sz, rgb(c.font.color)) for row in ws.iter_rows() for c in row)
        d_bg, d_n, d_sz, d_c = looks.most_common(1)[0][0]
        for row in ws.iter_rows():
            for c in row:
                v = c.value
                item = {"a": c.coordinate}
                if isinstance(v, ArrayFormula):
                    item["f"] = v.text.lstrip("=")
                elif isinstance(v, DataTableFormula):
                    pass
                elif isinstance(v, str) and v.startswith("="):
                    item["f"] = v[1:]
                elif isinstance(v, (int, float)) and not isinstance(v, bool):
                    if c.coordinate in keep:
                        item["v"] = v
                elif v is not None:
                    item["v"] = v
                font, fill, b = c.font, c.fill, c.border
                style = {k: x for k, x in (("b", bool(font.b)), ("i", bool(font.i))) if x}
                style.update({k: x for k, x, d in (("sz", font.sz, d_sz), ("n", font.name, d_n),
                                                   ("c", rgb(font.color), d_c)) if x != d})
                if fill is not None and fill.fill_type == "solid" and rgb(fill.fgColor) and rgb(fill.fgColor) != d_bg:
                    style["bg"] = rgb(fill.fgColor)
                edges = {side: [getattr(b, side).style, rgb(getattr(b, side).color)]
                         for side in ("top", "bottom", "left", "right") if getattr(b, side) is not None and getattr(b, side).style}
                if edges:
                    style["bd"] = edges
                if c.alignment is not None and (c.alignment.horizontal or c.alignment.indent):
                    style["al"] = [c.alignment.horizontal, c.alignment.indent or 0]
                if c.number_format != "General":
                    style["fmt"] = c.number_format
                if v is None and "bg" not in style and "bd" not in style:
                    continue  # nothing to draw
                item.update(style)
                cells.append(item)
        sheets.append({"name": ws.title, "cells": cells, "merged": [str(r) for r in ws.merged_cells.ranges],
                       "widths": {k: round(d.width, 1) for k, d in ws.column_dimensions.items() if d.width},
                       "look": {"bg": d_bg, "n": d_n, "sz": d_sz, "c": d_c}, "size": [ws.max_row, ws.max_column],
                       **row_heights(ws)})
    return {"sheets": sheets}
CUZK_WMS = "https://services.cuzk.cz/wms/wms.asp"

BACKGROUND = "#0d0d0d"
CITY = "#1a1a1a"
CITY_BORDER = "#2a2a2a"
PARK = "#131313"  # parks: a quiet background tone, darker than the city
ACCENT = "#8fe3a0"  # rozvojové obytné plochy, our targets
ORANGE = "#f08a3c"  # farmland (ZPF) highlights in the parcel list
PURPLE = "#b48cff"  # selected areas and parcels
BROWN = "#a8744c"  # transformační obytné plochy
TEXT = "#ececec"
MUTED = "#8a8a8a"
UI = "#f2f2f2"  # the interface's second colour (switches, sliders, links): white, the green stays on the map
TRACK = ("linear-gradient(90deg, transparent var(--a, 0%), #f2f2f2 var(--a, 0%), #f2f2f2 var(--b, 100%), transparent var(--b, 100%)),"
         " linear-gradient(180deg, transparent 1px, rgba(255,255,255,.18) 1px, rgba(255,255,255,.18) 3px, transparent 3px)")
# the price sliders: the track up to the knob thick and white, the rest a thin grey line

RSJ_HQ = (50.08915565, 14.43531183)  # Na Florenci 2116/15, Praha 1 (RÚIAN geocode)
RSJ_LOGO = Path(__file__).with_name("rsj-logo.svg")  # from rsj.com/layout/rsj-logo.svg
AIRPORT = (50.1008, 14.2632)  # Letiště Václava Havla, Praha-Ruzyně
SKY_ZOOM = 10  # zooming out to this (one step out from the start view) brings the clouds and the airport

# plane icon: Material Design "flight" (Apache 2.0)
PLANE = ('<svg viewBox="0 0 24 24"><path d="M21 16v-2l-8-5V3.5a1.5 1.5 0 0 0-3 0V9l-8 5v2l8-2.5V19l-2 1.5V22'
         'l3.5-1 3.5 1v-1.5L13 19v-5.5z"/></svg>')
# take-off paths from the airport (px, relative to it), roughly along the two runways
FLIGHTS = ["M0,0 C60,-20 140,-60 260,-150", "M0,0 C-70,25 -160,40 -290,10",
           "M0,0 C40,30 120,60 230,170", "M0,0 C-30,-40 -80,-110 -120,-230"]

WATER_FILL, WATER_EDGE = "#2b66a0", "#4a8fd6"
SMOOTH = 1.5  # Leaflet may simplify outlines by this many screen pixels while drawing: invisible, faster zooms

METRO_COLORS = {"A": "#1fa65a", "B": "#f6c21c", "C": "#e5352b", "D": "#3b8ef0"}  # official line colours
STOP_COLORS = {"A": "#7fd8a2", "B": "#fbe07f", "C": "#f2918a"}  # same, lighter, for the stops
TRAM, TRAM_STOP = "#ff9b2f", "#ffc98a"
BUS, BUS_STOP = "#3d8bff", "#9cc4ff"
TRAM_STOPS_FROM_ZOOM, BUS_STOPS_FROM_ZOOM = 13, 14  # stops only appear zoomed in, so they don't clutter
METRO_STOPS_FROM_ZOOM = TRAIN_STOPS_FROM_ZOOM = 12  # metro and train stations a step earlier

def tr(cs, en, sk):
    """A text in all three languages; the page's CSS shows the one chosen in the switcher (i18n.js)."""
    return f'<span class="l-cs">{cs}</span><span class="l-en">{en}</span><span class="l-sk">{sk}</span>'


GROUPS = [
    (tr("Rozvojové obytné", "Development residential", "Rozvojové obytné"), ACCENT, 0.75, True, lambda p: p["stabilita"] == 3 and p["vyuziti"] == 1),
    (tr("Transformační obytné", "Transformation residential", "Transformačné obytné"), BROWN, 0.75, True, lambda p: p["stabilita"] != 3 and p["vyuziti"] == 1),
]

# Panels: dark frosted glass in the manner of Rockaway Capital's site: smoky and half see-through, the
# map strongly blurred behind it, no border and no shadow
GLASS = ("background: rgba(16,16,16,.5); backdrop-filter: blur(14px) saturate(1); -webkit-backdrop-filter: blur(14px) saturate(1);"
         "border: none; box-shadow: none;")

I18N = I18N_JS.read_text(encoding="utf-8")  # inlined at the top of the page, before every other script
STYLE = f"""
<link href="https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  .leaflet-container {{ background: {BACKGROUND}; font-family: 'Hanken Grotesk', Arial, sans-serif; }}
  .leaflet-interactive:focus {{ outline: none; }}

  /* start screen: a black palantír in the middle; click it to enter the map */
  .ds-menu {{ position: fixed; inset: 0; z-index: 100000; display: flex; align-items: center; justify-content: center;
             --s: 1;  /* orb size: 1 on a desktop, .72 on a phone */
             --floor: calc(50% + 122px * var(--s));  /* where the orb touches the floor */
             /* the back wall of a dark studio: the orb lights it in a circle that falls off quickly, and a
                dim light high above throws a soft cone down it */
             background:
               radial-gradient(circle at 50% 50%, rgba(110,28,12,.12) 0%, rgba(60,14,6,.05) 22%, rgba(0,0,0,0) 48%),
               radial-gradient(ellipse 24% 72% at 50% -12%, rgba(220,226,242,.045) 0%, rgba(220,226,242,.014) 50%, rgba(0,0,0,0) 85%),
               #030303;
             transition: opacity 1s cubic-bezier(.4,0,.2,1) .6s, visibility 0s linear 1.6s; }}
  @media (max-width: 700px) {{ .ds-menu {{ --s: .72; }} }}
  /* the floor, seen in perspective: its own surface from where it meets the wall (just behind the orb)
     down to the bottom. Light lies on it as flattened ellipses, brightest where the orb touches it:
     the orb's warm pool, a wider warm spill, and the overhead light's faint patch. Near-black, warm, no grey */
  .ds-menu::after {{ content: ""; position: absolute; left: 0; right: 0; bottom: 0; z-index: 0; pointer-events: none;
                    top: calc(var(--floor) - 48px * var(--s));
                    --c: calc(48px * var(--s));  /* the contact point, measured from the top of the floor */
                    background:
                      radial-gradient(ellipse calc(150px * var(--s)) calc(20px * var(--s)) at 50% var(--c),
                                      rgba(255,110,50,.2) 0%, rgba(255,90,40,.06) 50%, rgba(0,0,0,0) 100%),
                      radial-gradient(ellipse calc(440px * var(--s)) calc(80px * var(--s)) at 50% calc(var(--c) + 6px),
                                      rgba(150,45,18,.2) 0%, rgba(90,25,10,.08) 45%, rgba(0,0,0,0) 100%),
                      radial-gradient(ellipse calc(260px * var(--s)) calc(42px * var(--s)) at 50% calc(var(--c) + 10px),
                                      rgba(220,226,242,.03) 0%, rgba(0,0,0,0) 100%),
                      linear-gradient(180deg, #0a0605 0%, #060404 35%, #030202 100%);
                    -webkit-mask: linear-gradient(180deg, transparent 0, #000 12px);
                            mask: linear-gradient(180deg, transparent 0, #000 12px); }}
  /* the orb's light spilling into the dark room: a wide warm glow that slowly breathes */
  .ds-menu::before {{ content: ""; position: absolute; inset: 0; z-index: 1; pointer-events: none;
                     background: radial-gradient(circle at 50% 50%, rgba(220,70,25,.5) 0%, rgba(170,45,18,.3) 12%,
                                 rgba(110,25,10,.15) 24%, rgba(50,12,5,.06) 38%, rgba(0,0,0,0) 56%);
                     animation: orb-breathe 6s ease-in-out infinite, orb-flicker-room 11s ease-in-out infinite; }}
  @keyframes orb-breathe {{ 0%, 100% {{ opacity: .75; transform: scale(.96); }} 50% {{ opacity: 1; transform: scale(1.04); }} }}
  .ds-menu.gone {{ opacity: 0; visibility: hidden; }}
  .orb-clouds {{ position: absolute; inset: 0; width: 100%; height: 100%; z-index: 1; pointer-events: none; }}
  .orb-lightning {{ position: absolute; inset: 0; width: 100%; height: 100%; z-index: 1; pointer-events: none; }}
  .orb-wrap {{ position: relative; z-index: 2; }}  /* above the floor (::after) and the room glow (::before) */
  /* dark glass: deep body, rim light (fresnel) and a cool bounce light at the bottom */
  .orb {{ position: relative; width: 240px; height: 240px; border-radius: 50%; cursor: pointer; overflow: hidden;
         background:
           radial-gradient(circle at 52% 58%, rgba(255,150,50,.38) 0%, rgba(200,60,20,.22) 18%, rgba(120,25,15,0) 45%),
           radial-gradient(circle at 50% 50%, rgba(0,0,0,0) 60%, rgba(120,130,160,.10) 68%, rgba(200,210,235,.22) 71.6%, rgba(0,0,0,0) 72%),
           radial-gradient(circle at 40% 36%, #16181e 0%, #0c0d11 38%, #050507 72%, #010101 100%);
         box-shadow: inset -26px -30px 54px rgba(0,0,0,.85),
                     inset 0 -8px 18px rgba(200,60,25,.18), 0 0 80px rgba(220,70,25,.16);
         transition: transform .6s cubic-bezier(.2,.8,.2,1), box-shadow .6s ease; }}
  /* smoke and fire turning slowly inside the glass (SVG noise, see the menu markup) */
  .orb-layer {{ position: absolute; inset: 0; width: 100%; height: 100%; border-radius: 50%; }}
  .orb-smoke {{ opacity: .85; animation: orb-swirl 60s linear infinite; }}
  .orb-fire {{ mix-blend-mode: screen; animation: orb-swirl 38s linear infinite reverse; }}
  .orb-core {{ mix-blend-mode: screen; filter: blur(1px); animation: orb-swirl 24s linear infinite; }}
  /* hover lures you in: the flames swell towards the glass and burn brighter, the glow flares */
  .orb-fire, .orb-core {{ transition: scale 1.4s cubic-bezier(.22,1,.36,1), filter 1.4s ease; }}
  .orb:hover .orb-fire, .orb:hover .orb-core {{ transition: scale 3.5s cubic-bezier(.45,0,.25,1), filter 3.5s ease; }}
  .orb:hover .orb-fire {{ scale: 1.12; filter: brightness(1.12) saturate(1.3); }}  /* stays orange, no yellow */
  .orb:hover .orb-core {{ scale: 1.2; filter: blur(1px) brightness(1.1) saturate(1.3); }}
  .orb-wrap:has(.orb:hover) .orb-halo {{ transition: opacity .6s ease, scale 6s cubic-bezier(.45,0,.25,1); }}
  .orb-wrap:has(.orb:hover) .orb-halo {{ scale: 1.9; }}  /* only grows: changing its blur every frame lagged */
  /* the glare follows the room's light: warm reflections flicker with the fire (same beat as the
     glow), and on hover, as the room fills with firelight, they slowly take over from the white ones */
  .glass-white {{ transition: opacity 3s ease; }}
  .glass-warm {{ animation: orb-flicker-room 11s ease-in-out infinite; transition: filter 3s ease; }}
  .orb:hover .glass-white {{ opacity: .35; transition: opacity 6s ease-in; }}
  .orb:hover .glass-warm {{ filter: brightness(2.2) saturate(1.2); transition: filter 6s ease-in; }}
  /* ...and the light slowly spills out of the glass until it fills the whole room */
  .ds-menu::before {{ transition: filter 2.5s ease, scale 3s cubic-bezier(.4,0,.2,1); }}  /* pulling back */
  .ds-menu:has(.orb:hover)::before {{ scale: 3.2; filter: brightness(1.7) saturate(1.2);
                                     transition: filter 6s ease-in, scale 7s cubic-bezier(.45,0,.25,1); }}  /* creeping out */
  @keyframes orb-swirl {{ to {{ transform: rotate(360deg); }} }}
  /* live light: a big blurred copy of the fire behind the glass, turning with it, so the glow on the
     room moves wherever the flames inside are */
  .orb-halo {{ position: absolute; left: 0; top: 0; width: 240px; height: 240px; pointer-events: none;
              transform: scale(2.3); filter: blur(34px) saturate(1.3); opacity: .8;
              transition: opacity .6s ease, scale 1.4s cubic-bezier(.22,1,.36,1), filter 1.4s ease;
              animation: orb-flicker 8s ease-in-out infinite; }}
  /* uneven steps, like a flame catching and dropping; the room glow below runs on a different beat */
  @keyframes orb-flicker {{
    0% {{ opacity: .78; transform: scale(2.3); }}    9% {{ opacity: .95; transform: scale(2.38); }}
    15% {{ opacity: .7; transform: scale(2.26); }}   27% {{ opacity: .88; transform: scale(2.34); }}
    33% {{ opacity: .74; transform: scale(2.28); }}  46% {{ opacity: 1; transform: scale(2.42); }}
    52% {{ opacity: .82; transform: scale(2.31); }}  64% {{ opacity: .68; transform: scale(2.25); }}
    71% {{ opacity: .9; transform: scale(2.36); }}   83% {{ opacity: .76; transform: scale(2.29); }}
    91% {{ opacity: .93; transform: scale(2.37); }}  100% {{ opacity: .78; transform: scale(2.3); }} }}
  @keyframes orb-flicker-room {{
    0%, 100% {{ opacity: .8; }} 13% {{ opacity: .95; }} 22% {{ opacity: .72; }} 38% {{ opacity: .9; }}
    47% {{ opacity: .78; }} 61% {{ opacity: 1; }} 69% {{ opacity: .74; }} 84% {{ opacity: .92; }} }}
  /* curved reflection across the top, like light on a glass dome */
  .orb-gloss {{ position: absolute; left: 13%; top: 5%; width: 74%; height: 46%; border-radius: 50%;
               background: radial-gradient(ellipse at 50% 38%, rgba(255,255,255,.12) 0%, rgba(255,255,255,.035) 45%, rgba(255,255,255,0) 70%); }}
  /* sharp specular highlight of the light source, plus a small secondary glint */
  .orb-spec {{ position: absolute; left: 25%; top: 15%; width: 22%; height: 13%; border-radius: 50%; transform: rotate(-30deg);
              background: radial-gradient(closest-side, rgba(255,255,255,.75) 0%, rgba(255,255,255,.3) 45%, rgba(255,255,255,0) 100%); }}
  .orb-spec::after {{ content: ""; position: absolute; left: 150%; top: 260%; width: 32%; height: 40%; border-radius: 50%;
                     background: radial-gradient(closest-side, rgba(255,235,230,.18), rgba(255,255,255,0)); }}
  .orb:hover {{ transform: scale(1.04); box-shadow: inset -26px -30px 54px rgba(0,0,0,.85),
                inset 0 -8px 18px rgba(220,70,25,.26), 0 0 120px rgba(230,80,25,.26); }}
  .orb-shadow {{ position: absolute; left: 50%; bottom: -20px; width: 230px; height: 38px; transform: translateX(-50%);
                border-radius: 50%; background: radial-gradient(closest-side, rgba(0,0,0,.95), rgba(0,0,0,0));
                filter: blur(5px); transition: opacity .6s ease; }}
  /* entering: we fly into the orb. It swells until it fills the screen while its glass fades, and Prague
     is inside it, small at first, unfolding to full size; then the controls slide in. The slow start of
     the curve hides the one heavy frame where the browser prepares the big orb */
  .ds-menu.gone .orb {{ transform: scale(6); opacity: 0;
                       transition: transform 1.7s cubic-bezier(.7,0,.2,1), opacity .7s ease .95s; }}
  .ds-menu.gone .orb-halo {{ opacity: 0; transition: opacity .6s ease; }}
  /* the orb's light floods the screen: a ready-made full-screen glow that only fades in (growing the
     room glow instead made the browser re-render it at four times the size, which stuttered) */
  .orb-flash {{ position: absolute; inset: 0; z-index: 1; pointer-events: none; opacity: 0; will-change: opacity;
               background: radial-gradient(circle at 50% 50%, rgba(255,125,55,.6) 0%, rgba(210,70,25,.42) 28%,
                           rgba(130,35,12,.28) 60%, rgba(50,12,5,.18) 100%); }}
  .ds-menu.gone .orb-flash {{ opacity: .7; transition: opacity 1.1s cubic-bezier(.4,0,.2,1) .3s; }}
  /* no scrollbars while the map is scaled, and the page behind it as dark as the map, so the map's
     edges vanish while it unfolds from inside the orb */
  html, body {{ overflow: hidden; background: {BACKGROUND}; }}
  /* smoothness: the orb and the map are their own ready-made layers before the click, and on the
     click every running effect freezes, so the move itself is only sliding and fading finished images */
  .orb-wrap, .orb, .orb-halo, .ds-menu::before {{ will-change: transform, opacity; }}
  .ds-menu.frozen *, .ds-menu.frozen::before, .ds-menu.frozen::after {{ animation-play-state: paused !important; }}
  /* opacity .001, not 0: the map is painted (invisibly) while the start screen shows, so revealing it
     costs nothing; it keeps its own layer afterwards, so it never has to be painted again all at once */
  .ds-menu ~ .folium-map {{ opacity: .001; transform: scale(.3); will-change: transform, opacity; }}
  .ds-menu.gone ~ .folium-map {{ opacity: 1; transform: none;
                                transition: opacity .9s ease .55s, transform 1.9s cubic-bezier(.7,0,.2,1) .1s; }}
  .ds-menu ~ .ds-title {{ opacity: .001; translate: 0 -10px; will-change: opacity, translate; }}  /* painted ahead, like the map */
  .ds-menu.gone ~ .ds-title {{ opacity: 1; translate: none;
                                transition: opacity .8s ease 2.1s, translate .8s cubic-bezier(.22,1,.36,1) 2.1s; }}  /* after the map has stopped: their glass blur over a moving map is costly */
  /* the map's own furniture (zoom buttons, scale bar, credits) waits too, instead of unfolding with it */
  .ds-menu ~ .folium-map .leaflet-control-container {{ opacity: 0; }}
  .ds-menu.gone ~ .folium-map .leaflet-control-container {{ opacity: 1; transition: opacity .8s ease 2.1s; }}
  .ds-menu.gone .orb-shadow {{ opacity: 0; }}

  /* the top bar, after Rockaway's: one strip of dark frosted glass across the top. Left the lighthouse of
     filter button, the name in the middle, the search and the lighthouse of Baldwin Alexandria on the right
     (its name slides out to the right from behind it on hover) */
  .ds-bar {{ position: fixed; top: 8px; left: 8px; right: 8px; height: 56px; z-index: 9999; box-sizing: border-box;
            padding: 0 8px; display: flex; align-items: center; gap: 12px;
            border-radius: 10px; font-family: 'Hanken Grotesk', Arial, sans-serif; {GLASS} }}
  .ds-brand {{ position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%); pointer-events: none;
              display: flex; align-items: baseline; gap: 12px; font-size: 15px; letter-spacing: .42em; white-space: nowrap;
              margin-right: -.42em; }}  /* the last letter's spacing would push the name off centre */
  .ds-brand b {{ font-weight: 600; color: {TEXT}; }}
  .ds-brand span {{ font-weight: 400; color: {MUTED}; }}
  .ds-left {{ display: flex; align-items: center; gap: 8px; min-width: 0; max-width: calc(50% - 170px); }}  /* ends where the name begins */
  .ds-lighthouse, .ds-lighthouse:visited, .ds-lighthouse:hover, .ds-lighthouse:focus, .ds-lighthouse:active {{ color: {TEXT} !important; }}
  .ds-lighthouse, .ds-lighthouse:visited {{ flex-shrink: 0; display: flex; align-items: center; height: 34px; border-radius: 6px;
                   background: rgba(255,255,255,.07); color: {TEXT}; text-decoration: none; overflow: hidden;
                   transition: transform 1.2s cubic-bezier(.16,1,.3,1); }}
  .ds-lighthouse .lh-icon {{ position: relative; z-index: 1; display: grid; place-items: center; width: 40px; height: 34px;
                            flex-shrink: 0; }}
  .ds-lighthouse svg {{ width: 20px; height: 20px; fill: none; stroke: currentColor; stroke-width: 1.4;
                       stroke-linecap: round; stroke-linejoin: round; }}
  .ds-lighthouse svg .fire {{ fill: currentColor; stroke: none; }}
  /* the name hides behind the lighthouse and slides out to the right on hover */
  .ds-lighthouse .lh-text {{ color: {TEXT}; max-width: 0; opacity: 0; transform: translateX(-24px); white-space: nowrap;
                            font-size: 11px; letter-spacing: .3em;
                            transition: max-width 3.2s cubic-bezier(.16,1,.3,1), opacity 2.2s ease .3s, transform 3.2s cubic-bezier(.16,1,.3,1),
                                        padding 3.2s cubic-bezier(.16,1,.3,1); }}
  .ds-lighthouse .lh-text b {{ font-weight: 600; color: {TEXT}; }}
  .ds-lighthouse .lh-text span {{ font-weight: 400; color: {MUTED}; }}
  .ds-lighthouse:hover {{ transform: scale(1.03); color: {TEXT}; text-decoration: none; }}  /* a slight pop, no colour
                                                                     change (Bootstrap would turn a hovered link blue) */
  .ds-lighthouse:hover .lh-text {{ max-width: 260px; opacity: 1; transform: none; padding-right: 16px; }}
  /* the controls grow a smidge under the mouse */
  .ds-toggle, .ds-search, .ds-select .seg, .ds-select .acre, .ds-select .clear, .deal .acre, .leaflet-bar a,
  .ds-drawer .leaflet-control-layers label {{ transition: transform .5s cubic-bezier(.16,1,.3,1); }}
  .ds-toggle:hover, .ds-search:hover, .ds-select .seg:hover, .ds-select .acre:hover, .ds-select .clear:hover,
  .deal .acre:hover, .leaflet-bar a:hover {{ transform: scale(1.03); }}
  .ds-drawer .leaflet-control-layers label {{ transform-origin: left center; }}
  .ds-drawer .leaflet-control-layers label:hover {{ transform: scale(1.03); }}
  .ds-right {{ margin-left: auto; display: flex; justify-content: flex-end; align-items: center; gap: 8px; }}
  .ds-search {{ position: relative; flex: 0 1 300px; min-width: 120px; }}
  @media (max-width: 1000px) {{ .ds-brand {{ font-size: 13px; letter-spacing: .3em; }} .ds-left {{ max-width: calc(50% - 140px); }} }}
  @media (max-width: 900px) {{ .ds-brand {{ display: none; }} }}  /* too narrow for the name between the two sides */
  .ds-search svg {{ position: absolute; left: 12px; top: 50%; width: 15px; height: 15px; transform: translateY(-50%);
                   stroke: {MUTED}; fill: none; stroke-width: 2; pointer-events: none; }}
  .ds-search input {{ width: 100%; height: 34px; box-sizing: border-box; padding: 0 34px 0 36px; border-radius: 6px;
                     border: 1px solid transparent; background: rgba(255,255,255,.07); color: {TEXT};
                     font: 400 12.5px 'Hanken Grotesk', Arial, sans-serif; outline: none; transition: border-color .2s, background .2s; }}
  .ds-search input::placeholder {{ color: {MUTED}; }}
  .ds-search input:focus {{ border-color: rgba(255,255,255,.4); background: rgba(255,255,255,.1); }}
  .ds-search kbd {{ position: absolute; right: 10px; top: 50%; transform: translateY(-50%); padding: 1px 6px;
                   border-radius: 4px; border: 1px solid rgba(255,255,255,.14); color: {MUTED}; font: 500 10px 'Hanken Grotesk', Arial; }}
  .ds-results {{ display: none; position: absolute; top: calc(100% + 12px); left: 0; width: 380px; max-height: 60vh;
                padding: 6px; box-sizing: border-box; overflow-y: auto; border-radius: 10px; {GLASS} background: rgba(16,16,16,.72);
                scrollbar-width: thin; scrollbar-color: #333333 transparent; }}
  .ds-results.open {{ display: block; }}
  .ds-hit {{ display: grid; grid-template-columns: 62px 1fr; column-gap: 10px; padding: 7px 8px; border-radius: 8px;
            cursor: pointer; }}
  .ds-hit.active, .ds-hit:hover {{ background: rgba(255,255,255,.06); }}
  .ds-tag {{ grid-row: span 2; align-self: center; justify-self: start; padding: 2px 7px; border-radius: 999px;
            border: 1px solid rgba(255,255,255,.1); font-size: 9px; letter-spacing: .1em; text-transform: uppercase;
            color: {MUTED}; }}
  .ds-main {{ font-size: 12px; color: {TEXT}; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .ds-sub {{ font-size: 10px; color: #5c6068; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}

  /* layer panel with toggle switches */
  .leaflet-control-layers {{ border-radius: 10px !important; padding: 12px 16px; {GLASS} border: none !important; }}
  .leaflet-control-layers label {{ font-size: 12px; font-weight: 400; letter-spacing: 0;
                                  color: {TEXT}; margin: 8px 0; cursor: pointer; }}
  .leaflet-control-layers label > span {{ display: flex; align-items: center; }}
  .leaflet-control-layers-separator {{ display: none; }}
  .leaflet-control-layers-selector {{ appearance: none; -webkit-appearance: none; position: relative; top: 0;
      width: 26px; height: 14px; margin: 0 12px 0 0; border-radius: 7px; background: #2e2e2e;
      cursor: pointer; flex-shrink: 0; transition: background .2s; }}
  .leaflet-control-layers-selector::after {{ content: ""; position: absolute; top: 2px; left: 2px;
      width: 10px; height: 10px; border-radius: 50%; background: #5c6068; transition: transform .2s, background .2s; }}
  .leaflet-control-layers-selector:checked {{ background: rgba(255,255,255,.28); }}
  .leaflet-control-layers-selector:checked::after {{ transform: translateX(12px); background: {UI}; }}
  .swatch {{ display: inline-block; width: 8px; height: 8px; border-radius: 2px; margin-right: 8px; }}
  .count {{ margin-left: auto; padding-left: 18px; color: {MUTED}; font-variant-numeric: tabular-nums; }}

  .leaflet-bar {{ border-radius: 8px !important; overflow: hidden; {GLASS} border: none !important; }}
  .leaflet-bar a {{ background: transparent !important; color: {TEXT} !important; border-bottom: 1px solid rgba(255,255,255,.06) !important; }}
  .leaflet-bar a:hover {{ color: {UI} !important; }}

  .leaflet-popup-content-wrapper, .leaflet-popup-tip {{ background: rgba(18,20,24,.94); color: {TEXT};
      box-shadow: 0 10px 40px rgba(0,0,0,.5); }}
  .leaflet-popup-content-wrapper {{ border-radius: 10px; border: none; }}
  .leaflet-popup-content {{ margin: 18px 20px; }}
  .leaflet-container a.leaflet-popup-close-button {{ color: {MUTED}; top: 8px; right: 8px; }}

  /* easter egg: zoomed out to SKY_ZOOM the screen fills with cartoon clouds, the airport glows above them */
  .ds-sky {{ position: absolute; inset: 0; z-index: 640; pointer-events: none; overflow: hidden;
            opacity: 0; transition: opacity 2s ease-out; }}
  .sky .ds-sky {{ opacity: 1; }}
  .ds-tint {{ position: absolute; inset: 0; background: linear-gradient(180deg, rgba(60,140,230,.62), rgba(130,190,245,.45)); }}
  /* two procedural cloud layers drifting at different speeds; each is two seamless tiles side by side */
  .ds-layer {{ position: absolute; top: 0; left: 0; width: 200%; height: 100%; display: flex;
              animation: drift linear infinite; will-change: transform; backface-visibility: hidden; }}
  .ds-layer svg {{ width: 50%; height: 100%; flex-shrink: 0; display: block; }}
  .ds-layer.back {{ opacity: .75; animation-duration: 240s; }}
  .ds-layer.front {{ opacity: .88; animation-duration: 150s; }}
  @keyframes drift {{ from {{ transform: translate3d(0,0,0); }} to {{ transform: translate3d(-50%,0,0); }} }}
  .leaflet-overlay-pane {{ transition: opacity 1.2s ease; }}
  .sky .leaflet-overlay-pane {{ opacity: .85; }}
  .ds-airport {{ position: absolute; left: 0; top: 0; z-index: 50; }}
  .ap-glow {{ position: absolute; left: -46px; top: -46px; width: 92px; height: 92px; border-radius: 50%;
             background: radial-gradient(closest-side, rgba(143,227,160,.75), rgba(143,227,160,0));
             animation: pulse 2.4s ease-in-out infinite; }}
  @keyframes pulse {{ 0%, 100% {{ transform: scale(.75); opacity: 1; }} 50% {{ transform: scale(1.35); opacity: .45; }} }}
  .ap-badge {{ position: absolute; left: 0; top: 0; transform: translate(-50%, -50%); padding: 6px 12px; border-radius: 999px;
              background: {ACCENT}; color: {BACKGROUND}; font: 800 13px 'Hanken Grotesk', Arial, sans-serif; letter-spacing: .22em;
              box-shadow: 0 0 0 3px rgba(255,255,255,.85), 0 0 26px {ACCENT}; }}
  .ap-name {{ position: absolute; left: 0; top: 22px; transform: translateX(-50%); white-space: nowrap; padding: 3px 9px;
             border-radius: 999px; background: rgba(255,255,255,.85); color: #1d2b45;
             font: 600 9px 'Hanken Grotesk', Arial, sans-serif; letter-spacing: .14em; text-transform: uppercase; }}
  .plane {{ position: absolute; left: 0; top: 0; width: 22px; height: 22px; margin: -11px 0 0 -11px;
           offset-rotate: auto 90deg; animation: fly 7s ease-in infinite; opacity: 0; }}
  .plane svg {{ width: 22px; height: 22px; fill: #24324a; filter: drop-shadow(0 0 2px #ffffff) drop-shadow(0 4px 6px rgba(0,0,0,.25)); }}
  @keyframes fly {{ 0% {{ offset-distance: 0%; opacity: 0; transform: scale(.6); }} 10% {{ opacity: 1; }}
                    80% {{ opacity: 1; }} 100% {{ offset-distance: 100%; opacity: 0; transform: scale(1.15); }} }}
  /* transfer stations: one dot split into both line colours */
  .transfer-icon {{ background: none; border: none; }}
  .transfer {{ width: 12px; height: 12px; padding: 2px; border-radius: 50%; box-sizing: border-box; }}
  .transfer i {{ display: block; width: 8px; height: 8px; border-radius: 50%; }}

  /* RSJ HQ easter egg: an almost invisible dot, the card only appears on hover */
  .hq-icon {{ background: none; border: none; }}
  .hq {{ position: relative; width: 22px; height: 22px; cursor: default; }}
  .hq-dot {{ position: absolute; left: 8px; top: 8px; width: 6px; height: 6px; border-radius: 50%;
            background: #3a3e46; transition: all .25s ease; }}
  .hq:hover .hq-dot {{ left: 5px; top: 5px; width: 12px; height: 12px; background: #ffffff;
                      box-shadow: 0 0 0 3px {BACKGROUND}, 0 0 0 5px #ffffff, 0 0 24px rgba(255,255,255,.8); }}
  .hq-card {{ position: absolute; left: 30px; top: -20px; display: flex; align-items: center; gap: 14px;
             padding: 12px 18px 12px 12px; border-radius: 10px; white-space: nowrap; {GLASS}
             opacity: 0; transform: translateX(-6px) scale(.94); transform-origin: left center;
             transition: opacity .25s ease, transform .25s ease; pointer-events: none; }}
  .hq.left .hq-card {{ left: auto; right: 30px; transform-origin: right center; }}
  .hq:hover .hq-card {{ opacity: 1; transform: none; }}
  .hq-logo svg {{ display: block; width: 44px; height: 44px; border-radius: 8px; }}
  .hq-text {{ font-family: 'Hanken Grotesk', Arial, sans-serif; line-height: 1.35; }}
  .hq-text small {{ display: block; font-size: 9px; font-weight: 500; letter-spacing: .18em; text-transform: uppercase;
                   color: {MUTED}; }}
  .hq-text b {{ display: block; margin-top: 3px; font-size: 13px; font-weight: 600; color: {TEXT}; }}
  .hq-text span {{ display: block; font-size: 11px; color: {MUTED}; }}

  /* price filter, stacked under the layer panel */
  .ds-filter {{ width: 240px; padding: 14px 16px; border-radius: 10px; color: {TEXT}; {GLASS}
               font-family: 'Hanken Grotesk', Arial, sans-serif; }}
  .ds-filter .ft {{ font-size: 11px; font-weight: 500; letter-spacing: .14em; text-transform: uppercase; }}
  .ds-filter .fv {{ display: block; margin-top: 6px; font-size: 13px; letter-spacing: 0; text-transform: none;
                   color: {UI}; font-variant-numeric: tabular-nums; }}
  .ds-filter label {{ display: flex; align-items: center; gap: 10px; margin-top: 10px; font-size: 11px;
                     letter-spacing: .1em; text-transform: uppercase; color: {MUTED}; }}
  /* slim price sliders: a hairline track and a small white knob */
  .ds-filter input[type=range] {{ flex: 1; height: 14px; margin: 0; background: none; -webkit-appearance: none; appearance: none; }}
  .ds-filter input[type=range]::-webkit-slider-runnable-track {{ height: 4px; border-radius: 2px; background: {TRACK}; }}
  .ds-filter input[type=range]::-moz-range-track {{ height: 4px; border-radius: 2px; background: {TRACK}; }}
  .ds-filter input[type=range]::-webkit-slider-thumb {{ -webkit-appearance: none; width: 11px; height: 11px; margin-top: -3.5px;
                                                       border: none; border-radius: 50%; background: {UI}; cursor: pointer; }}
  .ds-filter input[type=range]::-moz-range-thumb {{ width: 11px; height: 11px; border: none; border-radius: 50%; background: {UI}; cursor: pointer; }}
  .ds-filter label.chk {{ text-transform: none; letter-spacing: 0; font-size: 12px; }}
  .ds-filter input[type=checkbox] {{ accent-color: {UI}; }}
  .ds-filter .fc {{ margin-top: 10px; font-size: 12px; color: {TEXT}; }}
  .ds-filter .fs {{ margin-top: 4px; font-size: 9px; color: #5c6068; }}

  /* deal sheet in a side panel */
  .ds-panel {{ position: fixed; top: 72px; left: 8px; bottom: 8px; width: 390px; z-index: 9998;
              overflow-y: auto; padding: 22px 22px 18px; border-radius: 10px; {GLASS}
              transform: translateX(-120%); transition: transform .55s cubic-bezier(.22,1,.36,1); will-change: transform;
              font-family: 'Hanken Grotesk', Arial, sans-serif; scrollbar-width: thin; scrollbar-color: #333333 transparent; }}
  .ds-panel.open {{ transform: none; }}
  .ds-panel::-webkit-scrollbar {{ width: 6px; }}
  .ds-panel::-webkit-scrollbar-thumb {{ background: #333333; border-radius: 3px; }}
  .ds-close {{ position: absolute; top: 12px; right: 14px; background: none; border: none; color: {MUTED};
              font-size: 22px; line-height: 1; cursor: pointer; }}
  .ds-close:hover {{ color: {TEXT}; }}
  .ds-panel .deal .parcels {{ max-height: none; overflow: visible; margin-right: 0; padding-right: 0; }}
  .deal {{ font-size: 12px; color: {TEXT}; }}
  .deal .code {{ color: {UI}; font-size: 17px; font-weight: 600; letter-spacing: .03em; }}
  .deal .loc {{ font-size: 10px; letter-spacing: .18em; text-transform: uppercase; color: {MUTED}; margin-top: 2px; }}
  .deal .chips span {{ display: inline-block; margin: 10px 4px 0 0; padding: 3px 9px; border-radius: 999px;
                      border: 1px solid rgba(255,255,255,.1); font-size: 10px; color: {TEXT}; }}
  .deal .tiles {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-top: 12px; }}
  .deal .tile {{ background: rgba(255,255,255,.06); border-radius: 6px; padding: 9px 10px; }}
  .deal .tile b {{ display: block; font-size: 15px; font-weight: 600; font-variant-numeric: tabular-nums; }}
  .deal .tile small {{ font-size: 9px; letter-spacing: .12em; text-transform: uppercase; color: {MUTED}; }}
  .deal .sec {{ margin: 14px 0 4px; font-size: 9px; letter-spacing: .18em; text-transform: uppercase; color: {MUTED}; }}
  .deal .sec .note {{ letter-spacing: .06em; text-transform: none; }}
  .deal .drow {{ display: flex; justify-content: space-between; padding: 5px 0;
               border-bottom: 1px solid rgba(255,255,255,.05); }}
  .deal .drow span:first-child {{ color: {MUTED}; }}
  .deal .mdot {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }}
  .deal .warn {{ color: #f2918a; }}
  .deal .parcels {{ max-height: 168px; overflow-y: auto; margin-right: -6px; padding-right: 6px; }}
  .deal .psum {{ font-size: 10px; color: {MUTED}; padding: 2px 0 6px; }}
  .deal .prow {{ display: grid; grid-template-columns: 62px 82px 1fr auto; gap: 8px; align-items: center;
                padding: 5px 0; border-bottom: 1px solid rgba(255,255,255,.05); font-size: 11px;
                font-variant-numeric: tabular-nums; }}
  .deal .pnum {{ font-weight: 600; cursor: zoom-in; }}
  .deal .prow.hot {{ background: rgba(255,255,255,.08); }}
  .deal .prow {{ border-radius: 6px; transition: background .15s; }}
  .deal .pnum em {{ font-style: normal; font-weight: 500; color: {MUTED}; font-size: 9px; margin-left: 4px; }}
  .deal .parcels::-webkit-scrollbar {{ width: 6px; }}
  .deal .parcels::-webkit-scrollbar-thumb {{ background: #333333; border-radius: 3px; }}
  .deal .parcels {{ scrollbar-width: thin; scrollbar-color: #333333 transparent; }}
  .deal .ptype {{ color: {MUTED}; }}
  .deal .ptype i {{ font-style: normal; color: {ORANGE}; font-size: 9px; letter-spacing: .08em; margin-left: 3px; }}
  .deal a {{ color: {UI}; text-decoration: none; white-space: nowrap; }}
  .deal a:hover {{ text-decoration: underline; }}
  .deal .links {{ margin-top: 12px; font-size: 11px; }}
  .deal .muted {{ color: {MUTED}; padding: 4px 0; }}

  /* selection window (land assembly), bottom right */
  .ds-select {{ width: 310px; padding: 12px 14px; border-radius: 10px; color: {TEXT}; {GLASS}
               font-family: 'Hanken Grotesk', Arial, sans-serif; }}
  .ds-select .sh {{ display: flex; align-items: center; justify-content: space-between; }}
  .ds-select .ft {{ font-size: 11px; font-weight: 500; letter-spacing: .14em; text-transform: uppercase; }}
  .ds-select .seg {{ display: flex; gap: 2px; padding: 3px; border-radius: 999px; background: rgba(255,255,255,.05); }}
  .ds-select .seg button {{ border: none; background: none; color: {MUTED}; font: 500 11px 'Hanken Grotesk', Arial, sans-serif;
                           padding: 4px 12px; border-radius: 999px; cursor: pointer; transition: background .15s, color .15s; }}
  .ds-select .seg button:hover {{ color: {TEXT}; }}
  .ds-select .seg button.on {{ background: {PURPLE}; color: #0d0d0d; }}
  .ds-select .sbody {{ max-height: 52vh; overflow-y: auto; scrollbar-width: thin; scrollbar-color: #333333 transparent; }}
  .ds-select .sbody:empty {{ display: none; }}
  .ds-select .hint {{ margin-top: 10px; font-size: 12px; line-height: 1.5; color: {MUTED}; }}
  .ds-select .hint.explain {{ line-height: 1.55; }}
  .ds-select .hint.explain b {{ color: {TEXT}; font-weight: 600; }}
  .ds-select .srow {{ display: grid; grid-template-columns: 1fr auto auto; gap: 10px; align-items: center; padding: 5px 0;
                     border-bottom: 1px solid rgba(255,255,255,.05); font-size: 11px; font-variant-numeric: tabular-nums; }}
  .ds-select .srow.p {{ grid-template-columns: 1fr auto auto auto; }}
  .ds-select .sname {{ font-weight: 600; cursor: zoom-in; }}
  .ds-select .sname:hover {{ color: {PURPLE}; }}
  .ds-select .x {{ border: none; background: none; color: {MUTED}; cursor: pointer; font-size: 15px; line-height: 1; padding: 0 2px; }}
  .ds-select .x:hover {{ color: {TEXT}; }}
  .ds-select .clear {{ margin-top: 12px; width: 100%; padding: 7px; border-radius: 8px; border: 1px solid rgba(255,255,255,.1);
                      background: none; color: {TEXT}; font: 500 11px 'Hanken Grotesk', Arial, sans-serif; cursor: pointer; }}
  .ds-select .clear:hover {{ background: rgba(255,255,255,.05); }}
  /* Export to Acre: the one filled button, in the selection window and the deal sheet */
  .ds-select .acre, .deal .acre {{ margin-top: 12px; width: 100%; padding: 8px; border-radius: 8px; border: none;
                                  background: {UI}; color: #0d0d0d; font: 600 11px 'Hanken Grotesk', Arial, sans-serif;
                                  letter-spacing: .06em; cursor: pointer; transition: filter .15s; }}
  .ds-select .acre:hover, .deal .acre:hover {{ filter: brightness(1.1); }}
  .ds-select .acre:disabled, .deal .acre:disabled {{ filter: grayscale(.6); cursor: progress; }}
  .ds-select .acre + .clear {{ margin-top: 6px; }}
  .ds-select.busy {{ cursor: progress; }}
  .selecting, .selecting .leaflet-interactive {{ cursor: crosshair !important; }}

  /* filter window (layers, price filter, selection), under the icon at the top right and only as tall as
     its content. Opening, it unfolds out of the button's corner, its sections rise in one after another,
     and the icon's two slider knobs slide to their other ends */
  .ds-toggle {{ width: 34px; height: 34px; padding: 0; display: grid; place-items: center; border: none; border-radius: 6px;
               cursor: pointer; color: {TEXT}; background: rgba(255,255,255,.07); transition: color .2s, background .2s, transform .5s cubic-bezier(.16,1,.3,1); }}
  .ds-toggle:hover {{ background: rgba(255,255,255,.12); }}
  .ds-toggle svg {{ width: 18px; height: 18px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; }}
  .ds-toggle svg circle {{ transform-box: fill-box; transition: transform .55s cubic-bezier(.22,1,.36,1); }}
  .drawer-open .ds-toggle svg circle:first-of-type {{ transform: translateX(-6px); }}
  .drawer-open .ds-toggle svg circle:last-of-type {{ transform: translateX(6px); }}
  .ds-toggle:hover, .drawer-open .ds-toggle {{ color: {UI}; }}
  .ds-drawer {{ position: fixed; top: 72px; left: 8px; width: 320px; max-height: calc(100vh - 84px); z-index: 10000;
               box-sizing: border-box; padding: 2px 18px 14px; overflow-y: auto; {GLASS} background: rgba(16,16,16,.55);
               border-radius: 10px; transform-origin: top left;
               opacity: 0; visibility: hidden; transform: translateY(-10px) scale(.92);
               transition: opacity .3s ease, transform .5s cubic-bezier(.22,1,.36,1), visibility 0s linear .5s;
               font-family: 'Hanken Grotesk', Arial, sans-serif; scrollbar-width: thin; scrollbar-color: #333333 transparent; }}
  .drawer-open .ds-drawer {{ opacity: 1; visibility: visible; transform: none;
                            transition: opacity .3s ease, transform .55s cubic-bezier(.22,1,.36,1), visibility 0s; }}
  .ds-drawer > * {{ opacity: 0; transform: translateY(8px);
                   transition: opacity .3s ease, transform .45s cubic-bezier(.22,1,.36,1); }}
  .drawer-open .ds-drawer > * {{ opacity: 1; transform: none; }}
  .drawer-open .ds-drawer > :nth-child(1) {{ transition-delay: .06s; }}
  .drawer-open .ds-drawer > :nth-child(2) {{ transition-delay: .12s; }}
  .drawer-open .ds-drawer > :nth-child(3) {{ transition-delay: .18s; }}
  .drawer-open .ds-drawer > :nth-child(4) {{ transition-delay: .24s; }}
  .ds-drawer .dt {{ padding-top: 16px; font-size: 11px; font-weight: 500;
                   letter-spacing: .14em; text-transform: uppercase; color: {TEXT}; }}
  .ds-drawer > .leaflet-control {{ float: none; clear: none; margin: 0; width: auto; padding: 14px 0;
                                  background: none; box-shadow: none; backdrop-filter: none; -webkit-backdrop-filter: none;
                                  border: none !important;
                                  border-radius: 0 !important; }}
  .ds-drawer .ds-credits {{ padding: 12px 0 0; font-size: 10px; line-height: 1.5; color: #5a5a5a; }}
  .ds-drawer .ds-select .sbody {{ max-height: none; overflow: visible; }}

  /* phones: search across the top, the drawer and the deal sheet slide up from the bottom so the top of
     the map stays visible and tappable; pinch replaces the zoom buttons */
  @media (max-width: 700px) {{
    .ds-bar {{ padding: 0 6px; gap: 6px; }}
    .ds-left {{ gap: 6px; }}
    .ds-brand {{ display: none; }}
    .ds-left {{ flex: 1; max-width: none; }}
    .ds-search {{ flex: 1; width: auto; }}
    .ds-search kbd {{ display: none; }}
    .ds-results {{ position: fixed; top: 72px; left: 8px; right: 8px; width: auto; }}
    .ds-lighthouse:hover .lh-text {{ max-width: 0; opacity: 0; padding-right: 0; }}  /* no hover on a phone */
    .ds-search input {{ font-size: 16px; }}  /* 16px stops iOS from zooming into the field */
    .ds-results {{ max-height: 50vh; }}
    .leaflet-control-zoom {{ display: none; }}
    .ds-drawer {{ top: auto; bottom: 8px; left: 8px; right: 8px; width: auto; max-height: 62vh;
                 transform-origin: bottom center; transform: translateY(14px) scale(.97); }}

    .ds-panel {{ top: auto; left: 0; right: 0; bottom: 0; width: auto; max-height: 62vh; padding: 18px 16px 24px;
                border-radius: 18px 18px 0 0; transform: translateY(110%); }}
    .deal .prow {{ grid-template-columns: 54px 72px 1fr auto; gap: 6px; }}
    .orb-wrap {{ transform: scale(.72); }}
    .hq-card {{ display: none; }}
  }}

  .leaflet-tooltip {{ background: rgba(18,20,24,.94); color: {TEXT}; border: 1px solid rgba(255,255,255,.08);
                     border-radius: 8px; box-shadow: 0 6px 20px rgba(0,0,0,.4); font-size: 10px; font-weight: 600;
                     letter-spacing: .12em; text-transform: uppercase; }}
  .leaflet-tooltip:before {{ display: none; }}
  .popup-open .leaflet-tooltip {{ display: none; }}

  .leaflet-control-scale {{ margin: 0 0 14px 16px !important; }}
  .leaflet-control-scale-line {{ background: none; color: {MUTED}; border: 1px solid rgba(255,255,255,.35); border-top: none;
                                padding: 0 6px 2px; font: 500 10px 'Hanken Grotesk', Arial, sans-serif; letter-spacing: .08em; text-shadow: none; }}
  .leaflet-control-attribution {{ background: transparent !important; color: #5a5a5a; margin: 0 16px 12px 0 !important;
                                 font: 400 10px 'Hanken Grotesk', Arial, sans-serif; letter-spacing: .02em; }}
  .leaflet-control-attribution a {{ color: #7a7a7a; text-decoration: none; }}
  .leaflet-control-attribution a:hover {{ color: {TEXT}; }}
  /* languages: every static text is there three times, the chosen one shows */
  .l-cs, .l-en, .l-sk {{ display: none; }}
  html[lang=cs] .l-cs, html[lang=en] .l-en, html[lang=sk] .l-sk {{ display: inline; }}
  .skip-intro .ds-menu {{ display: none; }}
  .skip-intro .ds-menu ~ *, .skip-intro .ds-menu ~ * * {{ transition: none !important; }}
  /* without the start screen in front, the map stays hidden until it has its starting view, then fades in
     (otherwise its first drawn frame, a close-up, flashes up for a moment) */
  .skip-intro .ds-menu ~ .folium-map {{ opacity: 0 !important; }}
  .ds-menu.skipped ~ .folium-map {{ transition: opacity .45s ease !important; }}
  /* the language switcher at the far right of the bar; its list unfolds under it */
  .ds-lang {{ position: relative; }}
  .ds-lang-btn {{ width: 34px; height: 34px; padding: 0; border: none; border-radius: 6px; cursor: pointer;
                 background: rgba(255,255,255,.07); color: {TEXT}; font: 500 11px 'Hanken Grotesk', Arial, sans-serif; letter-spacing: .08em;
                 transition: transform .5s cubic-bezier(.16,1,.3,1); }}
  .ds-lang-btn:hover {{ transform: scale(1.03); }}
  .ds-lang-menu {{ position: absolute; top: calc(100% + 12px); right: 0; min-width: 150px; padding: 6px; box-sizing: border-box;
                  border-radius: 10px; {GLASS} background: rgba(16,16,16,.72); transform-origin: top right;
                  opacity: 0; visibility: hidden; transform: translateY(-6px) scale(.96);
                  transition: opacity .3s ease, transform .45s cubic-bezier(.16,1,.3,1), visibility 0s linear .45s; }}
  .ds-lang.open .ds-lang-menu {{ opacity: 1; visibility: visible; transform: none;
                                transition: opacity .3s ease, transform .45s cubic-bezier(.16,1,.3,1), visibility 0s; }}
  .ds-lang-menu button {{ display: flex; justify-content: space-between; width: 100%; padding: 8px 10px; border: none; border-radius: 6px;
                         background: none; color: {MUTED}; font: 400 12px 'Hanken Grotesk', Arial, sans-serif; cursor: pointer; text-align: left; }}
  .ds-lang-menu button:hover {{ background: rgba(255,255,255,.07); color: {TEXT}; }}
  .ds-lang-menu button.on {{ color: {TEXT}; font-weight: 500; }}
  .ds-lang-menu button small {{ font-size: 10px; letter-spacing: .08em; color: {MUTED}; }}
  /* phones: the name alone at the top, every button in one bar along the bottom where the thumbs are;
     the search results, the filter window, the deal sheet and the language list open above that bar */
  .ds-mbrand {{ display: none; }}
  @media (max-width: 700px) {{
    .ds-bar {{ top: auto; bottom: 8px; }}
    .ds-mbrand {{ display: block; position: fixed; top: 10px; left: 50%; transform: translateX(-50%); z-index: 9999;
                 padding: 9px 12px 9px 17px; border-radius: 8px; white-space: nowrap;
                 font: 400 13px 'Hanken Grotesk', Arial, sans-serif; letter-spacing: .34em; {GLASS} }}
    .ds-mbrand b {{ font-weight: 600; color: {TEXT}; }}
    .ds-mbrand span {{ color: {MUTED}; }}
    .ds-results {{ top: auto; bottom: 72px; }}
    .ds-drawer {{ bottom: 72px; max-height: calc(100vh - 140px); transform-origin: bottom left; }}
    .ds-panel {{ left: 8px; right: 8px; bottom: 72px; max-height: calc(100vh - 140px); border-radius: 10px; }}
    .ds-lang-menu {{ top: auto; bottom: calc(100% + 22px); transform-origin: bottom right; transform: translateY(6px) scale(.96); }}
  }}
  .ds-menu ~ .ds-mbrand {{ opacity: .001; }}
  .ds-menu.gone ~ .ds-mbrand {{ opacity: 1; transition: opacity .8s ease 2.1s; }}
</style>
<script>{I18N}</script>
<div class="ds-menu">
  <div class="orb-flash"></div><div class="orb-wrap"><div class="orb-halo">
    <svg class="orb-layer orb-fire" viewBox="0 0 200 200"><rect width="200" height="200" filter="url(#orb-fire-f)" mask="url(#orb-mask-all)"/></svg>
    <svg class="orb-layer orb-core" viewBox="0 0 200 200"><rect width="200" height="200" filter="url(#orb-core-f)" mask="url(#orb-mask-core)"/></svg></div>
  <div class="orb"><svg class="orb-layer orb-smoke" viewBox="0 0 200 200"><defs>
    <!-- each layer = a noise pattern bent by a second, slowly changing low-frequency "current" noise
         (feDisplacementMap), so the smoke and fire flow like ink in water instead of re-forming -->
    <filter id="orb-smoke-f" color-interpolation-filters="sRGB" x="0" y="0" width="100%" height="100%">
      <feTurbulence type="fractalNoise" baseFrequency="0.014 0.022" numOctaves="3" seed="5" result="n"/>
      <feTurbulence type="fractalNoise" baseFrequency="0.005" numOctaves="2" seed="8" result="flow">
        <animate attributeName="baseFrequency" dur="31s" repeatCount="indefinite" values="0.005;0.0068;0.0054;0.005"/></feTurbulence>
      <feDisplacementMap in="n" in2="flow" scale="46" xChannelSelector="R" yChannelSelector="G">
        <animate attributeName="scale" dur="23s" repeatCount="indefinite" values="46;70;38;46"/></feDisplacementMap>
      <feColorMatrix type="matrix" values="0 0 0 0 .1  0 0 0 0 .12  0 0 0 0 .2  2.2 0 0 0 -.95"/></filter>
    <filter id="orb-fire-f" color-interpolation-filters="sRGB" x="0" y="0" width="100%" height="100%">
      <feTurbulence type="fractalNoise" baseFrequency="0.02 0.03" numOctaves="3" seed="11" result="n"/>
      <feTurbulence type="fractalNoise" baseFrequency="0.006" numOctaves="2" seed="4" result="flow">
        <animate attributeName="baseFrequency" dur="24s" repeatCount="indefinite" values="0.006;0.0082;0.0064;0.006"/></feTurbulence>
      <feDisplacementMap in="n" in2="flow" scale="55" xChannelSelector="R" yChannelSelector="G">
        <animate attributeName="scale" dur="17s" repeatCount="indefinite" values="55;85;45;55"/></feDisplacementMap>
      <feColorMatrix type="matrix" values="0 0 0 0 .9  0 0 0 0 .12  0 0 0 0 .04  3 0 0 0 -1.45"/></filter>
    <filter id="orb-core-f" color-interpolation-filters="sRGB" x="0" y="0" width="100%" height="100%">
      <feTurbulence type="fractalNoise" baseFrequency="0.035" numOctaves="3" seed="2" result="n"/>
      <feTurbulence type="fractalNoise" baseFrequency="0.008" numOctaves="2" seed="13" result="flow">
        <animate attributeName="baseFrequency" dur="19s" repeatCount="indefinite" values="0.008;0.0105;0.0086;0.008"/></feTurbulence>
      <feDisplacementMap in="n" in2="flow" scale="40" xChannelSelector="R" yChannelSelector="G">
        <animate attributeName="scale" dur="13s" repeatCount="indefinite" values="40;64;34;40"/></feDisplacementMap>
      <feColorMatrix type="matrix" values="0 0 0 0 1  0 0 0 0 .5  0 0 0 0 .08  3.4 0 0 0 -1.5"/></filter>
    <radialGradient id="orb-m-all"><stop offset=".55" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>
    <radialGradient id="orb-m-core"><stop offset="0" stop-color="#fff"/><stop offset=".6" stop-color="#fff" stop-opacity=".25"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>
    <mask id="orb-mask-all"><circle cx="100" cy="100" r="96" fill="url(#orb-m-all)"/></mask>
    <mask id="orb-mask-core"><circle cx="100" cy="100" r="62" fill="url(#orb-m-core)"/></mask>
  </defs><rect width="200" height="200" filter="url(#orb-smoke-f)" mask="url(#orb-mask-all)"/></svg>
  <svg class="orb-layer orb-fire" viewBox="0 0 200 200"><rect width="200" height="200" filter="url(#orb-fire-f)" mask="url(#orb-mask-all)"/></svg>
  <svg class="orb-layer orb-core" viewBox="0 0 200 200"><rect width="200" height="200" filter="url(#orb-core-f)" mask="url(#orb-mask-core)"/></svg><svg class="orb-layer orb-glass" viewBox="0 0 200 200"><defs>
    <!-- the glass, in vectors so it stays sharp on any screen. Real glass reflects more the flatter you
         look at it, so it brightens towards the rim (fading out before the edge, no outline line); a
         faint sheen of the ceiling over the top; a window reflected as tapered curved panes on both
         sides, softly edged and fading at their ends; a glint at the top; a caustic at the bottom -->
    <radialGradient id="glass-fresnel" cx=".5" cy=".5" r=".5"><stop offset=".7" stop-color="#cfd8ff" stop-opacity="0"/>
      <stop offset=".9" stop-color="#cfd8ff" stop-opacity=".045"/><stop offset=".97" stop-color="#e6ecff" stop-opacity=".09"/>
      <stop offset="1" stop-color="#e6ecff" stop-opacity="0"/></radialGradient>
    <radialGradient id="glass-sky" cx=".5" cy=".2" r=".6"><stop offset="0" stop-color="#fff" stop-opacity=".1"/>
      <stop offset=".6" stop-color="#fff" stop-opacity=".03"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>
    <linearGradient id="glass-r" x1="1" y1="0" x2="0" y2="0"><stop offset="0" stop-color="#fff" stop-opacity=".7"/>
      <stop offset=".55" stop-color="#fff" stop-opacity=".22"/><stop offset="1" stop-color="#fff" stop-opacity=".04"/></linearGradient>
    <linearGradient id="glass-l" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity=".45"/>
      <stop offset=".55" stop-color="#fff" stop-opacity=".12"/><stop offset="1" stop-color="#fff" stop-opacity=".02"/></linearGradient>
    <radialGradient id="glass-c"><stop offset="0" stop-color="#fff" stop-opacity=".16"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>
    <linearGradient id="glass-fade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>
      <stop offset=".3" stop-color="#fff"/><stop offset=".7" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
    <mask id="glass-ends" maskContentUnits="objectBoundingBox"><rect width="1" height="1" fill="url(#glass-fade)"/></mask>
    <filter id="glass-soft" x="-10%" y="-10%" width="120%" height="120%"><feGaussianBlur stdDeviation=".55"/></filter>
    <!-- warm versions: the same reflections lit by the fire's light in the room, and the glowing floor
         reflected in the bottom of the glass; they flicker with the fire and take over on hover -->
    <linearGradient id="glass-warm-r" x1="1" y1="0" x2="0" y2="0"><stop offset="0" stop-color="#ff8a4a" stop-opacity=".55"/>
      <stop offset="1" stop-color="#ff6a2a" stop-opacity="0"/></linearGradient>
    <linearGradient id="glass-warm-l" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#ff8a4a" stop-opacity=".4"/>
      <stop offset="1" stop-color="#ff6a2a" stop-opacity="0"/></linearGradient>
    <linearGradient id="glass-floor" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#ff7a3a" stop-opacity=".42"/>
      <stop offset="1" stop-color="#ff5a20" stop-opacity="0"/></linearGradient>
  </defs>
    <circle cx="100" cy="100" r="100" fill="url(#glass-fresnel)"/>
    <ellipse cx="100" cy="46" rx="74" ry="42" fill="url(#glass-sky)"/>
    <g class="glass-white">
      <path filter="url(#glass-soft)" d="M142.7 19.7 A91 91 0 0 1 183.1 63 A150 150 0 0 0 142.7 19.7 Z" fill="url(#glass-r)" mask="url(#glass-ends)"/>
      <path filter="url(#glass-soft)" d="M185.5 68.9 A91 91 0 0 1 190.1 112.7 A150 150 0 0 0 185.5 68.9 Z" fill="url(#glass-r)" mask="url(#glass-ends)"/>
      <path filter="url(#glass-soft)" d="M24.5 147.2 A89 89 0 0 1 19.3 62.4 A170 170 0 0 0 24.5 147.2 Z" fill="url(#glass-l)" mask="url(#glass-ends)"/>
      <path filter="url(#glass-soft)" d="M37.6 34.6 A92 92 0 0 1 68.5 13.6" fill="none" stroke="#fff" stroke-opacity=".32" stroke-width="1.6" stroke-linecap="round"/>
    </g>
    <g class="glass-warm">
      <path filter="url(#glass-soft)" d="M142.7 19.7 A91 91 0 0 1 183.1 63 A150 150 0 0 0 142.7 19.7 Z" fill="url(#glass-warm-r)" mask="url(#glass-ends)"/>
      <path filter="url(#glass-soft)" d="M185.5 68.9 A91 91 0 0 1 190.1 112.7 A150 150 0 0 0 185.5 68.9 Z" fill="url(#glass-warm-r)" mask="url(#glass-ends)"/>
      <path filter="url(#glass-soft)" d="M24.5 147.2 A89 89 0 0 1 19.3 62.4 A170 170 0 0 0 24.5 147.2 Z" fill="url(#glass-warm-l)" mask="url(#glass-ends)"/>
      <path filter="url(#glass-soft)" d="M31.1 157.9 A90 90 0 0 0 168.9 157.9 A150 150 0 0 1 31.1 157.9 Z" fill="url(#glass-floor)"/>
    </g>
    <ellipse cx="100" cy="182" rx="34" ry="6" fill="url(#glass-c)"/></svg>
  </div><div class="orb-shadow"></div></div>
</div>
<div class="ds-mbrand"><b>BALDWIN</b> <span>PALANTIR</span></div>
<div class="ds-title ds-bar">
  <div class="ds-left">
    <div class="ds-search">
      <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>
      <input type="text" autocomplete="off" spellcheck="false">
      <kbd>/</kbd>
      <div class="ds-results"></div>
    </div>
  </div>
  <div class="ds-brand"><b>BALDWIN</b><span>PALANTIR</span></div>
  <div class="ds-right">
    <a class="ds-lighthouse" href="acre/" aria-label="Baldwin Acre">
      <span class="lh-icon"><svg viewBox="0 0 24 24"><path d="M2.5 15.5l9.5-5.2 9.5 5.2-9.5 5.2z"/>
        <path d="M7.2 12.9l9.5 5.2" stroke-dasharray="1.6 1.6"/><path d="M12 10.3V3.6l3.6 1.4-3.6 1.4"/>
        <circle cx="2.5" cy="15.5" r=".9" class="fire"/><circle cx="21.5" cy="15.5" r=".9" class="fire"/>
        <circle cx="12" cy="20.7" r=".9" class="fire"/></svg></span>
      <span class="lh-text"><b>BALDWIN</b> <span>ACRE</span></span>
    </a>
    <a class="ds-lighthouse" href="alexandria/" aria-label="Baldwin Alexandria">
      <span class="lh-icon"><svg viewBox="0 0 24 24"><path d="M6 22h12M7 22V15h10v7M8.5 15l1-6h5l1 6M10.5 9V6h3v3M11 22v-3h2v3"/>
        <path d="M12 2.2v1.6M8.6 3.2l1.6.9M15.4 3.2l-1.6.9"/><circle cx="12" cy="5" r=".9" class="fire"/></svg></span>
      <span class="lh-text"><b>BALDWIN</b> <span>ALEXANDRIA</span></span>
    </a>
    <div class="ds-lang">
      <button class="ds-lang-btn" aria-label="Language"><span class="l-cs">CS</span><span class="l-en">EN</span><span class="l-sk">SK</span></button>
      <div class="ds-lang-menu">
        <button data-lang="en">English <small>EN</small></button>
        <button data-lang="cs">Čeština <small>CS</small></button>
        <button data-lang="sk">Slovenčina <small>SK</small></button>
      </div>
    </div>
  </div>
</div>
"""


def _label(name, color, count, key=""):
    """A layer switch's label; the key (metro, tram …) lets the filter window put the switches in order."""
    return (f'<span class="swatch" data-k="{key}" style="background:{color}"></span>{name}'
            f'<span class="count">{count}</span>')


def _dash_empty(features):
    for f in features:  # empty values look nicer as a dash in the popup
        for key in ("z_max", "z_z", "v_z"):
            if f["properties"][key] is None:
                f["properties"][key] = "–"



def _add_metro(m, metro):
    """One layer: lines A/B/C (glow on hover), the planned line D dashed, and one named dot per station.
    The stations are their own sub-layer, shown only zoomed in. Returns (group, [(sub-layer, min zoom)])."""
    layer = folium.FeatureGroup(name=_label("Metro", "#e5352b", "A–D", "metro"), show=True)
    dots = folium.FeatureGroup(control=False)
    folium.GeoJson(
        metro["planned"],
        style_function=lambda _: {"color": METRO_COLORS["D"], "weight": 3, "opacity": 0.95, "dashArray": "6 6"},
        highlight_function=lambda _: {"weight": 6},
        tooltip=folium.GeoJsonTooltip(fields=["nazev"], labels=False),
    ).add_to(layer)
    folium.GeoJson(
        metro["lines"],
        style_function=lambda f: {"color": METRO_COLORS.get(f["properties"]["parametr"], TEXT), "weight": 3, "opacity": 0.95},
        highlight_function=lambda _: {"weight": 6},
        tooltip=folium.GeoJsonTooltip(fields=["parametr"], aliases=["Metro"]),
    ).add_to(layer)
    for s in metro["stations"]:
        tooltip = f"{s['name']} · {' · '.join(s['lines'])}"
        if len(s["lines"]) > 1:  # Můstek, Muzeum, Florenc: a dot split into both line colours
            # same look as a normal stop (line-colour rim, lighter fill), each half in its own line's colours
            l1, l2 = s["lines"][:2]
            rim = f"linear-gradient(90deg,{METRO_COLORS[l1]} 50%,{METRO_COLORS[l2]} 50%)"
            fill = f"linear-gradient(90deg,{STOP_COLORS[l1]} 50%,{STOP_COLORS[l2]} 50%)"
            folium.Marker(
                (s["lat"], s["lon"]), tooltip=tooltip,
                icon=folium.DivIcon(
                    html=f'<div class="transfer" style="background:{rim}"><i style="background:{fill}"></i></div>',
                    icon_size=(12, 12), icon_anchor=(6, 6), class_name="transfer-icon"),
            ).add_to(dots)
        else:
            line = s["lines"][0]
            folium.CircleMarker(
                (s["lat"], s["lon"]), radius=4, weight=2, fill=True, fill_opacity=1,
                color=METRO_COLORS[line], fill_color=STOP_COLORS[line], tooltip=tooltip,
            ).add_to(dots)
    dots.add_to(layer)
    layer.add_to(m)
    return layer, [(dots, METRO_STOPS_FROM_ZOOM)]


def _stop_dots(parent, stops, rim, fill, kind):
    """Stops as their own sub-layer of parent, so the script can show them only when zoomed in."""
    dots = folium.FeatureGroup(control=False)
    for s in stops:
        folium.CircleMarker(
            (s["lat"], s["lon"]), radius=2.5, weight=1.5, fill=True, fill_opacity=1, color=rim, fill_color=fill,
            tooltip=f"{s['name']} · {kind} {', '.join(s['lines'][:12])}{'…' if len(s['lines']) > 12 else ''}",
        ).add_to(dots)
    dots.add_to(parent)
    return dots


def _add_trams(m, trams):
    """Tram tracks in orange, with tram stops. Returns (group, [(sub-layer, min zoom)])."""
    group = folium.FeatureGroup(name=_label(tr("Tramvaje", "Trams", "Električky"), TRAM, len(trams["stops"]), "tram"), show=True)
    folium.GeoJson(
        trams["tracks"], interactive=False, smooth_factor=SMOOTH,
        style_function=lambda _: {"color": TRAM, "weight": 1.6, "opacity": 0.85},
    ).add_to(group)
    dots = _stop_dots(group, trams["stops"], TRAM, TRAM_STOP, "tram")
    group.add_to(m)
    return group, [(dots, TRAM_STOPS_FROM_ZOOM)]


def _add_buses(m, stops, routes):
    """Bus routes and stops in blue, both only when zoomed in. Returns (group, [(sub-layer, min zoom)])."""
    group = folium.FeatureGroup(name=_label(tr("Autobusy", "Buses", "Autobusy"), BUS, len(stops), "bus"), show=True)
    zoomed = []
    if routes:
        lines = folium.GeoJson(
            routes, interactive=False, smooth_factor=SMOOTH, style_function=lambda _: {"color": BUS, "weight": 1.2, "opacity": 0.7})
        lines.add_to(group)
        zoomed.append((lines, BUS_STOPS_FROM_ZOOM))
    zoomed.append((_stop_dots(group, stops, BUS, BUS_STOP, "bus"), BUS_STOPS_FROM_ZOOM))
    group.add_to(m)
    return group, zoomed


def _clip_lines(geo, inside):
    """A line GeoJSON cut to the parts inside a shape (here Prague's outline)."""
    from shapely.geometry import mapping, shape
    parts = []
    for f in geo["features"]:
        cut = shape(f["geometry"]).intersection(inside)
        parts += [g for g in getattr(cut, "geoms", [cut]) if g.geom_type == "LineString" and not g.is_empty]
    return {"type": "FeatureCollection",
            "features": [{"type": "Feature", "properties": {}, "geometry": mapping(g)} for g in parts]}


def _km(geo):
    """Total length of a line GeoJSON in whole km (equirectangular, plenty for a label)."""
    import math
    total = 0.0
    for f in geo["features"]:
        g = f["geometry"]
        if g["type"] not in ("LineString", "MultiLineString"):
            continue  # stations
        for line in (g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]):
            for (x1, y1), (x2, y2) in zip(line, line[1:]):
                kx = 111.32 * math.cos(math.radians((y1 + y2) / 2))
                total += math.hypot((x2 - x1) * kx, (y2 - y1) * 110.57)
    return round(total)


def _optional(load, what):
    """Loads an extra layer, or returns None (with a warning) if its service is down and nothing is cached."""
    try:
        return load()
    except Exception as err:
        print(f"warning: {what} skipped ({err})")
        return None


def build_map():
    areas, localities = add_screening(load_areas()), load_localities()
    parks, metro = _optional(load_parks, "parks"), _optional(load_metro, "metro")
    water = _optional(load_water, "water")
    # IPR's Vltava has patches; ČÚZK's river surfaces, clipped to Prague, fill them from underneath
    from shapely.geometry import shape
    from shapely.ops import unary_union
    prague = unary_union([shape(f["geometry"]).buffer(0) for f in localities["features"]])
    rivers = _optional(lambda: load_rivers(prague), "river (ZABAGED)")
    lines = _optional(load_motorways_rail, "motorways and railways (ZABAGED)")
    if lines:  # only inside Prague, like the rest of the map
        lines = tuple(_clip_lines(geo, prague) for geo in lines)
        # the train stations (PID) ride along with the railways: small dots with the name and lines on hover
        for st in _optional(load_train_stations, "train stations (PID)") or []:
            more = "…" if len(st["lines"]) > 12 else ""
            lines[1]["features"].append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [st["lon"], st["lat"]]},
                                         "properties": {"n": f'{st["name"]} · {", ".join(st["lines"][:12])}{more}'}})
    trams, buses = _optional(load_trams, "trams"), _optional(load_bus_stops, "bus stops")
    bus_routes = _optional(load_bus_routes, "bus routes")

    m = folium.Map(location=[50.075, 14.46], zoom_start=11, tiles=None, zoom_control=False)

    # Prague itself: dark neighbourhoods with faint borders (not a toggleable layer).
    city = folium.GeoJson(
        localities, name="Praha", control=False, smooth_factor=SMOOTH,
        style_function=lambda _: {"color": CITY_BORDER, "weight": 0.8, "fillColor": CITY, "fillOpacity": 1},
        tooltip=folium.GeoJsonTooltip(fields=["nazev"], labels=False),
    ).add_to(m)

    # Parks before the water: some park outlines reach over the Vltava and would cover it.
    park_geo = None
    if parks:
        park_layer = folium.FeatureGroup(name=_label(tr("Parky", "Parks", "Parky"), "#33363d", len(parks["features"]), "parks"), show=True)
        park_geo = folium.GeoJson(
            parks, smooth_factor=SMOOTH,
            style_function=lambda _: {"color": PARK, "weight": 0, "fillColor": PARK, "fillOpacity": 1},
            tooltip=folium.GeoJsonTooltip(fields=["nazev"], labels=False),
        ).add_to(park_layer)
        park_layer.add_to(m)

    # Only the Vltava, in blue; the small streams and ponds were a distraction. ZABAGED's river surfaces
    # carry no names in Prague, but the Vltava is by far their biggest connected piece (95 % of the area,
    # 22 km through the city). IPR's water breaks the river into pieces, so it only stands in when ZABAGED
    # is unavailable. Not interactive, so hovering shows the locality under it.
    source = rivers or water
    if source:
        from shapely.geometry import mapping
        merged = unary_union([shape(f["geometry"]) for f in source["features"]])
        vltava = max(getattr(merged, "geoms", [merged]), key=lambda part: part.area)
        folium.GeoJson(
            {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": mapping(vltava)}]},
            name="Vltava", control=False, interactive=False, smooth_factor=SMOOTH,
            style_function=lambda _: {"color": WATER_EDGE, "weight": 0.8, "fillColor": WATER_FILL, "fillOpacity": 1},
        ).add_to(m)

    for name, color, fill, show, belongs in GROUPS:
        features = [f for f in areas["features"] if belongs(f["properties"])]
        _dash_empty(features)
        layer = folium.FeatureGroup(name=_label(name, color, len(features)), show=show)
        folium.GeoJson(
            {"type": "FeatureCollection", "features": features}, smooth_factor=SMOOTH,
            style_function=lambda _, c=color, o=fill: {"color": c, "weight": 0.6, "fillColor": c, "fillOpacity": o},
            highlight_function=lambda _: {"weight": 2, "fillOpacity": 0.95},
            tooltip=folium.GeoJsonTooltip(fields=["area_code", "locality_name"], aliases=["", ""], labels=False),
        ).add_to(layer)  # click opens the deal sheet from deal_popup.js
        layer.add_to(m)

    zoom_layers = []  # (group, sub-layer, min zoom): shown or hidden by zoom in the script below
    if buses:
        group, subs = _add_buses(m, buses, bus_routes)
        zoom_layers += [(group, sub, z) for sub, z in subs]
    if trams:
        group, subs = _add_trams(m, trams)
        zoom_layers += [(group, sub, z) for sub, z in subs]
    if metro:
        group, subs = _add_metro(m, metro)
        zoom_layers += [(group, sub, z) for sub, z in subs]

    # RSJ headquarters as an easter egg: a barely visible dot that reveals a card with the logo on hover.
    # Straight on the map, so there's no layer toggle and the filter never touches it.
    logo = re.sub(r"<\?xml.*?\?>|<!--.*?-->", "", RSJ_LOGO.read_text(encoding="utf-8"), flags=re.S)
    folium.Marker(
        RSJ_HQ,
        icon=folium.DivIcon(
            html=f'<div class="hq"><span class="hq-dot"></span>'
                 f'<div class="hq-card"><div class="hq-logo">{logo}</div>'
                 f'<div class="hq-text"><small>Headquarters</small><b>Na Florenci 2116/15</b>'
                 f'<span>Praha 1 · Florentinum</span></div></div></div>',
            icon_size=(22, 22), icon_anchor=(11, 11), class_name="hq-icon"),
    ).add_to(m)

    # Cadastral parcels (white "inverse" style for the dark map), always on once zoomed in close.
    # Own pane above the filled shapes, so the lines stay visible but clicks still reach the areas.
    folium.map.CustomPane("parcels", z_index=450, pointer_events=False).add_to(m)
    folium.WmsTileLayer(
        pane="parcels",
        url=CUZK_WMS, layers="hranice_parcel_i,parcelni_cisla_i", fmt="image/png", transparent=True,
        name="Parcely", attr="© ČÚZK", overlay=True, control=False, opacity=0.55, min_zoom=17, max_zoom=21,
    ).add_to(m)

    control = folium.LayerControl(collapsed=False)
    control.add_to(m)
    m.get_root().header.add_child(folium.Element("<title>Baldwin Palantir</title>"))
    m.get_root().html.add_child(folium.Element(STYLE))
    # start screen: clicking the orb (or pressing Enter) fades it away into the map
    m.get_root().html.add_child(folium.Element("""<script>
      (function () {
        const menu = document.querySelector('.ds-menu');
        menu.title = t('Vstoupit', 'Enter', 'Vstúpiť');
        // after a language switch, or coming back from Alexandria or Acre, the page goes straight to the map;
        // the map script shows it once its starting view is set (below, on load)
        if (document.documentElement.classList.contains('skip-intro')) {
          menu.classList.add('frozen', 'gone', 'skipped');
          menu.style.display = 'none';
        }
        // Entering is pure transform/opacity work for the graphics card: the costly effects (the fire's
        // morphing SVG filters, the CSS flicker) freeze on the click, and once the move is over the start
        // screen is switched off completely so nothing keeps running behind the map.
        // Freezing costs one slow frame, so it happens first, while nothing moves yet; the move starts two
        // frames later. It starts on the press, not the release, which gives the freeze a head start.
        const enter = () => {
          if (menu.classList.contains('frozen')) return;
          menu.querySelectorAll('svg').forEach((s) => s.pauseAnimations && s.pauseAnimations());
          menu.classList.add('frozen');
          requestAnimationFrame(() => requestAnimationFrame(() => {
            menu.classList.add('gone');
            setTimeout(() => { menu.style.display = 'none'; }, 2300);
          }));
        };
        menu.querySelector('.orb').addEventListener('pointerdown', enter);
        document.addEventListener('keydown', (e) => { if (e.key === 'Enter') enter(); });
      })();
    </script>""" + f"<script>{LIGHTNING_JS.read_text(encoding='utf-8')}</script>"
                 + f"<script>{CLOUDS_JS.read_text(encoding='utf-8')}</script>"))
    # Explicit zoom range (otherwise Leaflet takes min zoom 17 from the parcel layer), and the
    # visible credit the CC BY licence requires for the IPR data.
    name = m.get_name()
    deal_js = (DEAL_JS.read_text(encoding="utf-8").replace("__MAP__", name)
               .replace("__METRO__", json.dumps(METRO_COLORS))
               .replace("__ACCENT__", json.dumps(ACCENT)).replace("__ORANGE__", json.dumps(ORANGE)))
    filter_js = FILTER_JS.read_text(encoding="utf-8").replace("__MAP__", name)
    import shutil
    shutil.copy2(acre_copy(), OUT.with_name(ACRE_EXAMPLE))
    # the link carries the file's fingerprint, so a browser never hands out an older copy of the model
    example_v = hashlib.sha1(OUT.with_name(ACRE_EXAMPLE).read_bytes()).hexdigest()[:10]
    # the Baldwin Acre page, its own folder of the site like Alexandria; it shows that same example
    site_acre = OUT.with_name("acre")
    site_acre.mkdir(exist_ok=True)
    (site_acre / "index.html").write_text((ACRE_WEB_DIR / "index.html").read_text(encoding="utf-8")
                                          .replace("__MODEL__", f"../{ACRE_EXAMPLE}?v={example_v}"), encoding="utf-8")
    shutil.copy2(ACRE_WEB_DIR / "viewer.js", site_acre / "viewer.js")
    site_alexandria = OUT.with_name("alexandria")
    site_alexandria.mkdir(exist_ok=True)
    for file in ALEXANDRIA_FILES:
        shutil.copy2(ALEXANDRIA_DIR / file, site_alexandria / file)
    export_js = (EXPORT_JS.read_text(encoding="utf-8").replace("__ACRE__", json.dumps(acre_template(), ensure_ascii=False))
                 .replace("__EXAMPLE__", json.dumps({"area": ACRE_EXAMPLE_AREA, "file": f"{ACRE_EXAMPLE}?v={example_v}"})))
    select_js = SELECT_JS.read_text(encoding="utf-8").replace("__MAP__", name).replace("__PURPLE__", json.dumps(PURPLE))
    drawer_js = DRAWER_JS.read_text(encoding="utf-8").replace("__MAP__", name)
    stations = [{k: s[k] for k in ("name", "lines", "lat", "lon")} for s in (metro or {}).get("stations", [])]
    search_js = (SEARCH_JS.read_text(encoding="utf-8").replace("__MAP__", name)
                 .replace("__STATIONS__", json.dumps(stations, ensure_ascii=False)))
    sky_js = (SKY_JS.read_text(encoding="utf-8").replace("__MAP__", name)
              .replace("__AIRPORT__", json.dumps(AIRPORT)).replace("__PLANE__", json.dumps(PLANE))
              .replace("__FLIGHTS__", json.dumps(FLIGHTS)).replace("__SKY_ZOOM__", str(SKY_ZOOM)))
    park_js = f"{park_geo.get_name()}.bringToBack();" if park_geo else ""
    # motorways and railways: written as their own files beside the page, loaded by lines.js
    line_layers = []
    if lines:
        for geo, file, label, style in (
                (lines[0], "motorways.geojson", tr("Dálnice", "Motorways", "Diaľnice"),
                 {"color": "#9a9a9a", "weight": 1.8, "opacity": 0.85}),
                (lines[1], "rail.geojson", tr("Železnice", "Railways", "Železnice"),
                 {"color": "#e87ab4", "weight": 1.2, "stop": "#f6bcd9", "stopsFrom": TRAIN_STOPS_FROM_ZOOM})):  # pink: the one colour no other layer uses
            OUT.with_name(file).write_text(json.dumps(geo, separators=(",", ":")), encoding="utf-8")
            v = hashlib.sha1(OUT.with_name(file).read_bytes()).hexdigest()[:10]
            key = "motorway" if file.startswith("motorways") else "rail"
            line_layers.append({"file": f"{file}?v={v}", "style": style,
                                "label": _label(label, style["color"], f"{_km(geo):,} km".replace(",", " "), key)})
    lines_js = (LINES_JS.read_text(encoding="utf-8").replace("__MAP__", name).replace("__CONTROL__", control.get_name())
                .replace("__LAYERS__", json.dumps(line_layers, ensure_ascii=False))) if line_layers else ""
    zoom_js = "\n".join(
        f"if (z >= {z}) {g.get_name()}.addLayer({s.get_name()}); else {g.get_name()}.removeLayer({s.get_name()});"
        for g, s, z in zoom_layers)
    m.get_root().script.add_child(folium.Element(f"""
    window.addEventListener('load', () => {{
        {name}.setMinZoom({SKY_ZOOM});
        // smoother wheel zoom: smaller steps that may land between whole zoom levels
        Object.assign({name}.options, {{ zoomSnap: 0.25, wheelPxPerZoomLevel: 110 }});
        {name}.setMaxZoom(20);
        {name}.setView([50.075, 14.46], 11);
        // the starting view is set: a page that skipped the start screen may show the map now
        setTimeout(() => document.documentElement.classList.remove('skip-intro'), 60);  // a timer, not a frame: also runs in a background tab
        // no line of credits on the map: the CC BY credits sit at the foot of the filter window (drawer.js)
        {name}.attributionControl.remove();
        // tram stops, bus stops and bus routes only once zoomed in
        const byZoom = () => {{
            const z = {name}.getZoom();
            {zoom_js}
        }};
        {name}.on('zoomend', byZoom);
        byZoom();
        // a layer switched back on is drawn on top; keep parks and the city under the water and the rest
        window.baldwinCityBack = () => {{ {park_js} {city.get_name()}.bringToBack(); }};
        {name}.on('overlayadd', () => {{ window.baldwinLinesBack && window.baldwinLinesBack(); window.baldwinCityBack(); }});
        // RSJ card opens to the left when it would run into the panels on the right
        const rightPanels = document.querySelector('.leaflet-top.leaflet-right');
        document.querySelectorAll('.hq').forEach((el) => el.addEventListener('mouseenter', () => {{
            const card = el.querySelector('.hq-card').offsetWidth + 40;
            const limit = Math.min(window.innerWidth, rightPanels.getBoundingClientRect().left);
            el.classList.toggle('left', el.getBoundingClientRect().right + card > limit);
        }}));
        // hide hover labels while a popup is open, so they don't sit on top of it
        {name}.on('popupopen', () => {name}.getContainer().classList.add('popup-open'));
        {name}.on('popupclose', () => {name}.getContainer().classList.remove('popup-open'));
        {export_js}
        {deal_js}
        {filter_js}
        {search_js}
        {select_js}
        {lines_js}
        {drawer_js}
        {sky_js}
    }});"""))
    m.save(OUT)
    # folium writes the GeoJSON with spaces after every "," and ":"; dropping them (only next to numbers,
    # brackets and quotes, so text like "Praha, Libuš" is left alone) and cutting coordinates to 5
    # decimals (~1 m) keeps the page well under 10 MB
    html = OUT.read_text(encoding="utf-8")
    html = re.sub(r'(?<=[\d\]}"]), (?=[\[{"\-\d])', ",", html)
    html = re.sub(r'(?<=")\: (?=[\[{"\-\dtfn])', ":", html)
    html = re.sub(r'(?<=[\[,])(-?\d{1,3}\.\d{5})\d+', r"\1", html)
    # IPR's bookkeeping fields and empty values are never shown; Czech letters as text, not á
    html = re.sub(r'"(SHAPE__Area|SHAPE__Length|globalid|objectid)":("[^"]*"|[\d.]+),|"\w+":null,', "", html)
    html = re.sub(r"\\u([0-9a-f]{4})", lambda u: chr(int(u[1], 16)) if 0xA0 <= int(u[1], 16) < 0x2000 else u[0], html)
    OUT.write_text(html, encoding="utf-8")
    return OUT


if __name__ == "__main__":
    print(f"Saved {build_map()}")
