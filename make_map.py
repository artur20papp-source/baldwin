"""Builds index.html: a minimal dark map of Prague's development areas with cadastral parcels.

No street base map: Prague is drawn from its own plan data (neighbourhoods, parks, areas).
Clicking an area opens a deal sheet (deal_popup.js) that also lists its parcels live from ČÚZK.
"""
import json
import re
from pathlib import Path

import folium

from mpp import (load_areas, load_bus_routes, load_bus_stops, load_localities, load_metro, load_parks,
                 load_rivers, load_trams, load_water)
from screening import add_screening

OUT = Path(__file__).with_name("index.html")  # index.html so GitHub Pages serves it at the site root
DEAL_JS = Path(__file__).with_name("deal_popup.js")
FILTER_JS = Path(__file__).with_name("price_filter.js")
SEARCH_JS = Path(__file__).with_name("search.js")
SKY_JS = Path(__file__).with_name("sky.js")
SELECT_JS = Path(__file__).with_name("selection.js")
DRAWER_JS = Path(__file__).with_name("drawer.js")
LIGHTNING_JS = Path(__file__).with_name("lightning.js")
CUZK_WMS = "https://services.cuzk.cz/wms/wms.asp"

BACKGROUND = "#0b0c0e"
CITY = "#17191d"
CITY_BORDER = "#262930"
PARK = "#111316"  # parks: a quiet background tone, darker than the city
ACCENT = "#8fe3a0"  # rozvojové obytné plochy, our targets
ORANGE = "#f08a3c"  # farmland (ZPF) highlights in the parcel list
PURPLE = "#b48cff"  # selected areas and parcels
BROWN = "#a8744c"  # transformační obytné plochy
TEXT = "#ececec"
MUTED = "#7d828c"

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

METRO_COLORS = {"A": "#1fa65a", "B": "#f6c21c", "C": "#e5352b", "D": "#3b8ef0"}  # official line colours
STOP_COLORS = {"A": "#7fd8a2", "B": "#fbe07f", "C": "#f2918a"}  # same, lighter, for the stops
TRAM, TRAM_STOP = "#ff9b2f", "#ffc98a"
BUS, BUS_STOP = "#3d8bff", "#9cc4ff"
TRAM_STOPS_FROM_ZOOM, BUS_STOPS_FROM_ZOOM = 13, 14  # stops only appear zoomed in, so they don't clutter

GROUPS = [
    ("Rozvojové obytné", ACCENT, 0.75, True, lambda p: p["stabilita"] == 3 and p["vyuziti"] == 1),
    ("Transformační obytné", BROWN, 0.75, True, lambda p: p["stabilita"] != 3 and p["vyuziti"] == 1),
]

GLASS = ("background: rgba(18,20,24,.72); backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);"
         "border: 1px solid rgba(255,255,255,.06); box-shadow: 0 10px 40px rgba(0,0,0,.45);")

STYLE = f"""
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  .leaflet-container {{ background: {BACKGROUND}; font-family: Inter, Arial, sans-serif; }}
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
             transition: opacity .9s ease .25s, visibility .9s ease .25s; }}
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
  .ds-menu.gone .orb-halo {{ opacity: 0; }}
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
  .ds-menu.gone .orb {{ transform: scale(6); opacity: 0; transition: transform .9s cubic-bezier(.6,0,.4,1), opacity .9s ease; }}
  .ds-menu.gone .orb-shadow {{ opacity: 0; }}

  /* title panel: wordmark + search */
  .ds-title {{ position: fixed; top: 16px; left: 64px; z-index: 9999; width: 330px; padding: 16px 16px 14px;
              border-radius: 16px; box-sizing: border-box; font-family: Inter, Arial, sans-serif; {GLASS} }}
  .ds-brand {{ display: flex; align-items: baseline; gap: 10px; padding: 0 4px 12px; font-size: 14px;
              letter-spacing: .34em; }}
  .ds-brand b {{ font-weight: 600; color: {TEXT}; }}
  .ds-brand span {{ font-weight: 400; color: {MUTED}; }}
  .ds-search {{ position: relative; }}
  .ds-search svg {{ position: absolute; left: 11px; top: 50%; width: 14px; height: 14px; transform: translateY(-50%);
                   stroke: {MUTED}; fill: none; stroke-width: 2; pointer-events: none; }}
  .ds-search input {{ width: 100%; box-sizing: border-box; padding: 9px 34px 9px 32px; border-radius: 10px;
                     border: 1px solid rgba(255,255,255,.07); background: rgba(255,255,255,.04); color: {TEXT};
                     font: 400 12px Inter, Arial, sans-serif; outline: none; transition: border-color .2s, background .2s; }}
  .ds-search input::placeholder {{ color: #5c6068; }}
  .ds-search input:focus {{ border-color: rgba(143,227,160,.45); background: rgba(255,255,255,.06); }}
  .ds-search kbd {{ position: absolute; right: 9px; top: 50%; transform: translateY(-50%); padding: 1px 6px;
                   border-radius: 5px; border: 1px solid rgba(255,255,255,.12); color: #5c6068; font: 500 10px Inter, Arial; }}
  .ds-results {{ display: none; margin-top: 8px; max-height: 330px; overflow-y: auto; scrollbar-width: thin;
                scrollbar-color: #2e3138 transparent; }}
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
  .leaflet-control-layers {{ border-radius: 14px !important; padding: 12px 16px; {GLASS}
                            border: 1px solid rgba(255,255,255,.06) !important; }}
  .leaflet-control-layers label {{ font-size: 10px; font-weight: 500; letter-spacing: .14em;
                                  text-transform: uppercase; color: {TEXT}; margin: 8px 0; cursor: pointer; }}
  .leaflet-control-layers label > span {{ display: flex; align-items: center; }}
  .leaflet-control-layers-separator {{ display: none; }}
  .leaflet-control-layers-selector {{ appearance: none; -webkit-appearance: none; position: relative; top: 0;
      width: 26px; height: 14px; margin: 0 12px 0 0; border-radius: 7px; background: #2a2d33;
      cursor: pointer; flex-shrink: 0; transition: background .2s; }}
  .leaflet-control-layers-selector::after {{ content: ""; position: absolute; top: 2px; left: 2px;
      width: 10px; height: 10px; border-radius: 50%; background: #5c6068; transition: transform .2s, background .2s; }}
  .leaflet-control-layers-selector:checked {{ background: rgba(143,227,160,.28); }}
  .leaflet-control-layers-selector:checked::after {{ transform: translateX(12px); background: {ACCENT}; }}
  .swatch {{ display: inline-block; width: 8px; height: 8px; border-radius: 2px; margin-right: 8px; }}
  .count {{ margin-left: auto; padding-left: 18px; color: {MUTED}; font-variant-numeric: tabular-nums; }}

  .leaflet-bar {{ border-radius: 12px !important; overflow: hidden; {GLASS} border: 1px solid rgba(255,255,255,.06) !important; }}
  .leaflet-bar a {{ background: transparent !important; color: {TEXT} !important; border-bottom: 1px solid rgba(255,255,255,.06) !important; }}
  .leaflet-bar a:hover {{ color: {ACCENT} !important; }}

  .leaflet-popup-content-wrapper, .leaflet-popup-tip {{ background: rgba(18,20,24,.94); color: {TEXT};
      box-shadow: 0 10px 40px rgba(0,0,0,.5); }}
  .leaflet-popup-content-wrapper {{ border-radius: 14px; border: 1px solid rgba(255,255,255,.06); }}
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
              background: {ACCENT}; color: {BACKGROUND}; font: 800 13px Inter, Arial, sans-serif; letter-spacing: .22em;
              box-shadow: 0 0 0 3px rgba(255,255,255,.85), 0 0 26px {ACCENT}; }}
  .ap-name {{ position: absolute; left: 0; top: 22px; transform: translateX(-50%); white-space: nowrap; padding: 3px 9px;
             border-radius: 999px; background: rgba(255,255,255,.85); color: #1d2b45;
             font: 600 9px Inter, Arial, sans-serif; letter-spacing: .14em; text-transform: uppercase; }}
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
             padding: 12px 18px 12px 12px; border-radius: 14px; white-space: nowrap; {GLASS}
             opacity: 0; transform: translateX(-6px) scale(.94); transform-origin: left center;
             transition: opacity .25s ease, transform .25s ease; pointer-events: none; }}
  .hq.left .hq-card {{ left: auto; right: 30px; transform-origin: right center; }}
  .hq:hover .hq-card {{ opacity: 1; transform: none; }}
  .hq-logo svg {{ display: block; width: 44px; height: 44px; border-radius: 8px; }}
  .hq-text {{ font-family: Inter, Arial, sans-serif; line-height: 1.35; }}
  .hq-text small {{ display: block; font-size: 9px; font-weight: 500; letter-spacing: .18em; text-transform: uppercase;
                   color: {MUTED}; }}
  .hq-text b {{ display: block; margin-top: 3px; font-size: 13px; font-weight: 600; color: {TEXT}; }}
  .hq-text span {{ display: block; font-size: 11px; color: {MUTED}; }}

  /* price filter, stacked under the layer panel */
  .ds-filter {{ width: 240px; padding: 14px 16px; border-radius: 14px; color: {TEXT}; {GLASS}
               font-family: Inter, Arial, sans-serif; }}
  .ds-filter .ft {{ font-size: 10px; font-weight: 500; letter-spacing: .14em; text-transform: uppercase; }}
  .ds-filter .fv {{ display: block; margin-top: 6px; font-size: 13px; letter-spacing: 0; text-transform: none;
                   color: {ACCENT}; font-variant-numeric: tabular-nums; }}
  .ds-filter label {{ display: flex; align-items: center; gap: 10px; margin-top: 10px; font-size: 10px;
                     letter-spacing: .1em; text-transform: uppercase; color: {MUTED}; }}
  .ds-filter input[type=range] {{ flex: 1; accent-color: {ACCENT}; }}
  .ds-filter label.chk {{ text-transform: none; letter-spacing: 0; font-size: 11px; }}
  .ds-filter input[type=checkbox] {{ accent-color: {ACCENT}; }}
  .ds-filter .fc {{ margin-top: 10px; font-size: 11px; color: {TEXT}; }}
  .ds-filter .fs {{ margin-top: 4px; font-size: 9px; color: #5c6068; }}

  /* deal sheet in a side panel */
  .ds-panel {{ position: fixed; top: 140px; left: 16px; bottom: 16px; width: 390px; z-index: 9998;
              overflow-y: auto; padding: 22px 22px 18px; border-radius: 16px; {GLASS}
              transform: translateX(-120%); transition: transform .55s cubic-bezier(.22,1,.36,1); will-change: transform;
              font-family: Inter, Arial, sans-serif; scrollbar-width: thin; scrollbar-color: #2e3138 transparent; }}
  .ds-panel.open {{ transform: none; }}
  .ds-panel::-webkit-scrollbar {{ width: 6px; }}
  .ds-panel::-webkit-scrollbar-thumb {{ background: #2e3138; border-radius: 3px; }}
  .ds-close {{ position: absolute; top: 12px; right: 14px; background: none; border: none; color: {MUTED};
              font-size: 22px; line-height: 1; cursor: pointer; }}
  .ds-close:hover {{ color: {TEXT}; }}
  .ds-panel .deal .parcels {{ max-height: none; overflow: visible; margin-right: 0; padding-right: 0; }}
  .deal {{ font-size: 12px; color: {TEXT}; }}
  .deal .code {{ color: {ACCENT}; font-size: 17px; font-weight: 600; letter-spacing: .03em; }}
  .deal .loc {{ font-size: 10px; letter-spacing: .18em; text-transform: uppercase; color: {MUTED}; margin-top: 2px; }}
  .deal .chips span {{ display: inline-block; margin: 10px 4px 0 0; padding: 3px 9px; border-radius: 999px;
                      border: 1px solid rgba(255,255,255,.1); font-size: 10px; color: {TEXT}; }}
  .deal .tiles {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; margin-top: 12px; }}
  .deal .tile {{ background: rgba(255,255,255,.04); border-radius: 10px; padding: 9px 10px; }}
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
  .deal .prow.hot {{ background: rgba(143,227,160,.08); }}
  .deal .prow {{ border-radius: 6px; transition: background .15s; }}
  .deal .pnum em {{ font-style: normal; font-weight: 500; color: {MUTED}; font-size: 9px; margin-left: 4px; }}
  .deal .parcels::-webkit-scrollbar {{ width: 6px; }}
  .deal .parcels::-webkit-scrollbar-thumb {{ background: #2e3138; border-radius: 3px; }}
  .deal .parcels {{ scrollbar-width: thin; scrollbar-color: #2e3138 transparent; }}
  .deal .ptype {{ color: {MUTED}; }}
  .deal .ptype i {{ font-style: normal; color: {ORANGE}; font-size: 9px; letter-spacing: .08em; margin-left: 3px; }}
  .deal a {{ color: {ACCENT}; text-decoration: none; white-space: nowrap; }}
  .deal a:hover {{ text-decoration: underline; }}
  .deal .links {{ margin-top: 12px; font-size: 11px; }}
  .deal .muted {{ color: {MUTED}; padding: 4px 0; }}

  /* selection window (land assembly), bottom right */
  .ds-select {{ width: 310px; padding: 12px 14px; border-radius: 14px; color: {TEXT}; {GLASS}
               font-family: Inter, Arial, sans-serif; }}
  .ds-select .sh {{ display: flex; align-items: center; justify-content: space-between; }}
  .ds-select .ft {{ font-size: 10px; font-weight: 500; letter-spacing: .14em; text-transform: uppercase; }}
  .ds-select .seg {{ display: flex; gap: 2px; padding: 3px; border-radius: 999px; background: rgba(255,255,255,.05); }}
  .ds-select .seg button {{ border: none; background: none; color: {MUTED}; font: 500 11px Inter, Arial, sans-serif;
                           padding: 4px 12px; border-radius: 999px; cursor: pointer; transition: background .15s, color .15s; }}
  .ds-select .seg button:hover {{ color: {TEXT}; }}
  .ds-select .seg button.on {{ background: {PURPLE}; color: #0b0c0e; }}
  .ds-select .sbody {{ max-height: 52vh; overflow-y: auto; scrollbar-width: thin; scrollbar-color: #2e3138 transparent; }}
  .ds-select .sbody:empty {{ display: none; }}
  .ds-select .hint {{ margin-top: 10px; font-size: 11px; color: {MUTED}; }}
  .ds-select .srow {{ display: grid; grid-template-columns: 1fr auto auto; gap: 10px; align-items: center; padding: 5px 0;
                     border-bottom: 1px solid rgba(255,255,255,.05); font-size: 11px; font-variant-numeric: tabular-nums; }}
  .ds-select .srow.p {{ grid-template-columns: 1fr auto auto auto; }}
  .ds-select .sname {{ font-weight: 600; cursor: zoom-in; }}
  .ds-select .sname:hover {{ color: {PURPLE}; }}
  .ds-select .x {{ border: none; background: none; color: {MUTED}; cursor: pointer; font-size: 15px; line-height: 1; padding: 0 2px; }}
  .ds-select .x:hover {{ color: {TEXT}; }}
  .ds-select .clear {{ margin-top: 12px; width: 100%; padding: 7px; border-radius: 8px; border: 1px solid rgba(255,255,255,.1);
                      background: none; color: {TEXT}; font: 500 11px Inter, Arial, sans-serif; cursor: pointer; }}
  .ds-select .clear:hover {{ background: rgba(255,255,255,.05); }}
  .ds-select.busy {{ cursor: progress; }}
  .selecting, .selecting .leaflet-interactive {{ cursor: crosshair !important; }}

  /* filter drawer on the right (layers, price filter, selection), opened by the icon at the top right */
  .ds-toggle {{ position: fixed; top: 16px; right: 16px; z-index: 10001; width: 44px; height: 44px; padding: 0;
               display: grid; place-items: center; border-radius: 14px; cursor: pointer; color: {TEXT}; {GLASS}
               transition: color .2s, background .2s; }}
  .ds-toggle svg {{ width: 20px; height: 20px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; }}
  .ds-toggle:hover, .drawer-open .ds-toggle {{ color: {ACCENT}; }}
  .ds-drawer {{ position: fixed; top: 0; right: 0; bottom: 0; width: 360px; z-index: 10000; box-sizing: border-box;
               padding: 16px 20px 20px; overflow-y: auto; {GLASS} background: rgba(14,15,18,.94);
               border: none; border-left: 1px solid rgba(255,255,255,.06); border-radius: 0;
               transform: translateX(100%); transition: transform .6s cubic-bezier(.22,1,.36,1); will-change: transform;
               font-family: Inter, Arial, sans-serif; scrollbar-width: thin; scrollbar-color: #2e3138 transparent; }}
  .drawer-open .ds-drawer {{ transform: none; }}
  .ds-drawer .dt {{ height: 44px; display: flex; align-items: center; font-size: 11px; font-weight: 600;
                   letter-spacing: .22em; text-transform: uppercase; color: {TEXT}; margin-bottom: 6px; }}
  .ds-drawer > .leaflet-control {{ float: none; clear: none; margin: 0; width: auto; padding: 16px 0;
                                  background: none; box-shadow: none; backdrop-filter: none; -webkit-backdrop-filter: none;
                                  border: none !important; border-top: 1px solid rgba(255,255,255,.06) !important;
                                  border-radius: 0 !important; }}
  .ds-drawer .ds-select .sbody {{ max-height: none; overflow: visible; }}

  /* phones: search across the top, the drawer and the deal sheet slide up from the bottom so the top of
     the map stays visible and tappable; pinch replaces the zoom buttons */
  @media (max-width: 700px) {{
    .ds-title {{ top: 12px; left: 12px; right: 68px; width: auto; padding: 12px; }}
    .ds-brand {{ font-size: 12px; padding-bottom: 10px; }}
    .ds-search input {{ font-size: 16px; }}  /* 16px stops iOS from zooming into the field */
    .ds-results {{ max-height: 50vh; }}
    .leaflet-control-zoom {{ display: none; }}
    .ds-toggle {{ top: 12px; right: 12px; }}
    .ds-drawer {{ top: auto; height: 62vh; width: 100%; border-left: none; border-top: 1px solid rgba(255,255,255,.08);
                 border-radius: 18px 18px 0 0; padding-top: 6px; transform: translateY(100%); }}
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

  .leaflet-control-scale-line {{ background: rgba(18,20,24,.7); color: {MUTED}; border-color: #3a3d44; }}
  .leaflet-control-attribution {{ background: transparent !important; color: #4d5158; font-size: 9px; }}
  .leaflet-control-attribution a {{ color: #4d5158; }}
</style>
<div class="ds-menu" title="Vstoupit">
  <div class="orb-wrap"><div class="orb-halo">
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
<div class="ds-title">
  <div class="ds-brand"><b>BALDWIN</b><span>PALANTIR</span></div>
  <div class="ds-search">
    <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>
    <input type="text" placeholder="Plocha, lokalita, metro, adresa…" autocomplete="off" spellcheck="false">
    <kbd>/</kbd>
  </div>
  <div class="ds-results"></div>
</div>
"""


def _label(name, color, count):
    return f'<span class="swatch" style="background:{color}"></span>{name}<span class="count">{count}</span>'


def _dash_empty(features):
    for f in features:  # empty values look nicer as a dash in the popup
        for key in ("z_max", "z_z", "v_z"):
            if f["properties"][key] is None:
                f["properties"][key] = "–"



def _add_metro(m, metro):
    """One layer: lines A/B/C (glow on hover), the planned line D dashed, and one named dot per station."""
    layer = folium.FeatureGroup(name=_label("Metro", "#e5352b", "A–D"), show=True)
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
            ).add_to(layer)
        else:
            line = s["lines"][0]
            folium.CircleMarker(
                (s["lat"], s["lon"]), radius=4, weight=2, fill=True, fill_opacity=1,
                color=METRO_COLORS[line], fill_color=STOP_COLORS[line], tooltip=tooltip,
            ).add_to(layer)
    layer.add_to(m)


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
    group = folium.FeatureGroup(name=_label("Tramvaje", TRAM, len(trams["stops"])), show=True)
    folium.GeoJson(
        trams["tracks"], interactive=False,
        style_function=lambda _: {"color": TRAM, "weight": 1.6, "opacity": 0.85},
    ).add_to(group)
    dots = _stop_dots(group, trams["stops"], TRAM, TRAM_STOP, "tram")
    group.add_to(m)
    return group, [(dots, TRAM_STOPS_FROM_ZOOM)]


def _add_buses(m, stops, routes):
    """Bus routes and stops in blue, both only when zoomed in. Returns (group, [(sub-layer, min zoom)])."""
    group = folium.FeatureGroup(name=_label("Autobusy", BUS, len(stops)), show=True)
    zoomed = []
    if routes:
        lines = folium.GeoJson(
            routes, interactive=False, style_function=lambda _: {"color": BUS, "weight": 1.2, "opacity": 0.7})
        lines.add_to(group)
        zoomed.append((lines, BUS_STOPS_FROM_ZOOM))
    zoomed.append((_stop_dots(group, stops, BUS, BUS_STOP, "bus"), BUS_STOPS_FROM_ZOOM))
    group.add_to(m)
    return group, zoomed


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
    trams, buses = _optional(load_trams, "trams"), _optional(load_bus_stops, "bus stops")
    bus_routes = _optional(load_bus_routes, "bus routes")

    m = folium.Map(location=[50.075, 14.46], zoom_start=11, tiles=None, control_scale=True)

    # Prague itself: dark neighbourhoods with faint borders (not a toggleable layer).
    city = folium.GeoJson(
        localities, name="Praha", control=False,
        style_function=lambda _: {"color": CITY_BORDER, "weight": 0.8, "fillColor": CITY, "fillOpacity": 1},
        tooltip=folium.GeoJsonTooltip(fields=["nazev"], labels=False),
    ).add_to(m)

    # Parks before the water: some park outlines reach over the Vltava and would cover it.
    park_geo = None
    if parks:
        park_layer = folium.FeatureGroup(name=_label("Parky", "#33363d", len(parks["features"])), show=True)
        park_geo = folium.GeoJson(
            parks,
            style_function=lambda _: {"color": PARK, "weight": 0, "fillColor": PARK, "fillOpacity": 1},
            tooltip=folium.GeoJsonTooltip(fields=["nazev"], labels=False),
        ).add_to(park_layer)
        park_layer.add_to(m)

    # Water in blue so the Vltava stands out; not interactive, so hovering shows the locality under it.
    if water:
        if rivers:  # under IPR's water, no outline: only shows where IPR's river has a gap
            folium.GeoJson(
                rivers, name="Řeky", control=False, interactive=False,
                style_function=lambda _: {"weight": 0, "fillColor": WATER_FILL, "fillOpacity": 1},
            ).add_to(m)
        folium.GeoJson(
            water, name="Voda", control=False, interactive=False,
            style_function=lambda _: {"color": WATER_EDGE, "weight": 0.8, "fillColor": WATER_FILL, "fillOpacity": 1},
        ).add_to(m)

    for name, color, fill, show, belongs in GROUPS:
        features = [f for f in areas["features"] if belongs(f["properties"])]
        _dash_empty(features)
        layer = folium.FeatureGroup(name=_label(name, color, len(features)), show=show)
        folium.GeoJson(
            {"type": "FeatureCollection", "features": features},
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
        _add_metro(m, metro)

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

    folium.LayerControl(collapsed=False).add_to(m)
    m.get_root().header.add_child(folium.Element("<title>Baldwin Palantir</title>"))
    m.get_root().html.add_child(folium.Element(STYLE))
    # start screen: clicking the orb (or pressing Enter) fades it away into the map
    m.get_root().html.add_child(folium.Element("""<script>
      (function () {
        const menu = document.querySelector('.ds-menu');
        const enter = () => menu.classList.add('gone');
        menu.querySelector('.orb').addEventListener('click', enter);
        document.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !menu.classList.contains('gone')) enter(); });
      })();
    </script>""" + f"<script>{LIGHTNING_JS.read_text(encoding='utf-8')}</script>"))
    # Explicit zoom range (otherwise Leaflet takes min zoom 17 from the parcel layer), and the
    # visible credit the CC BY licence requires for the IPR data.
    name = m.get_name()
    deal_js = (DEAL_JS.read_text(encoding="utf-8").replace("__MAP__", name)
               .replace("__METRO__", json.dumps(METRO_COLORS))
               .replace("__ACCENT__", json.dumps(ACCENT)).replace("__ORANGE__", json.dumps(ORANGE)))
    filter_js = FILTER_JS.read_text(encoding="utf-8").replace("__MAP__", name)
    select_js = SELECT_JS.read_text(encoding="utf-8").replace("__MAP__", name).replace("__PURPLE__", json.dumps(PURPLE))
    drawer_js = DRAWER_JS.read_text(encoding="utf-8").replace("__MAP__", name)
    stations = [{k: s[k] for k in ("name", "lines", "lat", "lon")} for s in (metro or {}).get("stations", [])]
    search_js = (SEARCH_JS.read_text(encoding="utf-8").replace("__MAP__", name)
                 .replace("__STATIONS__", json.dumps(stations, ensure_ascii=False)))
    sky_js = (SKY_JS.read_text(encoding="utf-8").replace("__MAP__", name)
              .replace("__AIRPORT__", json.dumps(AIRPORT)).replace("__PLANE__", json.dumps(PLANE))
              .replace("__FLIGHTS__", json.dumps(FLIGHTS)).replace("__SKY_ZOOM__", str(SKY_ZOOM)))
    park_js = f"{park_geo.get_name()}.bringToBack();" if park_geo else ""
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
        {name}.attributionControl.addAttribution('datový podklad © IPR Praha (CC BY) · zastávky © PID (CC BY) · Vltava © ČÚZK ZABAGED (CC BY)');
        // tram stops, bus stops and bus routes only once zoomed in
        const byZoom = () => {{
            const z = {name}.getZoom();
            {zoom_js}
        }};
        {name}.on('zoomend', byZoom);
        byZoom();
        // a layer switched back on is drawn on top; keep parks and the city under the water and the rest
        {name}.on('overlayadd', () => {{ {park_js} {city.get_name()}.bringToBack(); }});
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
        {deal_js}
        {filter_js}
        {search_js}
        {select_js}
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
