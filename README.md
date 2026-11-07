# Baldwin

**Land-development screening and appraisal for Prague, built entirely on open public data.**

Baldwin answers three questions about a piece of land in Prague: *what may be built there, what is it worth, and does the project pay?* It joins the city's zoning plan, the official land-price map, the national cadastre and public transport data into one interactive map, connects that map to a full Excel development appraisal, and documents every input in a source library that can be queried in plain language.

| Part | Purpose | Link |
|---|---|---|
| **Baldwin Palantir** | Map-based screening of all 1,144 residential development and transformation areas in Prague | [open map](https://artur20papp-source.github.io/baldwin/) |
| **Baldwin Acre** | Development appraisal model (Excel), shown read-only with its formulas | [open model](https://artur20papp-source.github.io/baldwin/acre/) |
| **Baldwin Alexandria** | Assistant that answers only from the project's documented sources | [open chat](https://artur20papp-source.github.io/baldwin/alexandria/) |

Available in English, Czech and Slovak.

### The names

- **Baldwin.** The name of the crusader kings of Jerusalem: five of them ruled between 1100 and 1186. The first, Baldwin I, took the port of Acre in 1104 and built a kingdom along a coast whose harbours traded with Alexandria and the whole eastern Mediterranean. The project takes the name for its three parts: a view over the land, its measure and money, and its library.
- **Palantir.** In Tolkien's *The Lord of the Rings* the *palantíri* are the seeing-stones: crystal orbs through which their keepers watch distant lands. The map is that stone for Prague: one view over every development area of the city, which is why it opens with an orb.
- **Acre.** Two meanings at once. The acre is the old measure of land, from the Old English *æcer*, a field. And Acre (Akko) is the ancient port city on the coast of the Holy Land, taken in 1104 by King Baldwin I of Jerusalem and later the capital of the crusader kingdom, the place where its trade and money came ashore. Baldwin Acre is the part that measures land in money: what a site costs, what it earns and whether it pays.
- **Alexandria.** The Library of Alexandria set out to hold all the knowledge of its time, and the Pharos, the lighthouse of Alexandria, guided ships into its harbour. Baldwin Alexandria is the project's library: every source, every assumption and how it moves the results, behind a lighthouse icon.

---

## Baldwin Palantir: the map

**Coverage.** Every residential area of the Metropolitní plán (592 *rozvojové*, development, and 552 *transformační*, transformation), drawn over the plan's 743 localities, with the metro (lines A–C and the planned D), trams, buses, motorways, railways and train stations.

**For each area** the panel shows:

| Figure | How it is obtained |
|---|---|
| Site area (*výměra*) | measured from the outline in the Czech national grid S-JTSK (EPSG:5514); web-map coordinates overstate areas in Prague by about 2.4× |
| Regulations Zz, Vz, Zmax | from the plan's own attributes |
| Regulated floor area | HPP reg. = výměra × Zz × Vz (Metropolitní plán, čl. 96 odst. 4) |
| Land price | area-weighted average of the official price map (*cenová mapa*) zones inside the area, or within 500 m where none lie inside |
| Metro access | straight-line distance in S-JTSK to the nearest station and to the planned line D |
| Flood risk | share of the area inside a designated flood zone |
| Parcels | loaded live from the ČÚZK cadastre: number, area, land type, farmland (ZPF) share, link to the owner record |

**Land assembly.** Several areas or individual parcels can be selected as one site; the selection totals area, HPP, farmland and price-map value.

**Export to Baldwin Acre.** Any area or selection is written into the appraisal model as an Excel file, with the facts the map knows (site area, Zz, land price, farmland share) filled in and sourced, and every project assumption left for the analyst. The worked example (Šeberov, area 414/267/5033) downloads as the complete model.

## Baldwin Acre: the appraisal model

Four appraisals of the same site, each with KPIs, a yearly cash flow and an IRR sensitivity grid:

| Sheet | Scenario | Šeberov result |
|---|---|---|
| Analysis | service the land and sell 89 plots | profit 214.4 M Kč · IRR 8.1 % |
| Analysis (Loan) | the same with a land loan (60 % of the land price) | profit 112.4 M Kč · equity IRR 8.3 % |
| Analysis H | build and sell 89 family houses | profit 131.6 M Kč · IRR 3.5 % |
| Analysis H (Loan) | houses with the land loan and a construction loan (60 % of construction costs, drawn as built) | profit −40.1 M Kč · equity IRR −2.2 % |

The last case shows **negative leverage**: the houses earn about 3.5 % a year while debt costs 6.4–7.9 % (3M PRIBOR 3.94 % plus a margin), so every borrowed crown lowers the return; the loans only reduce the equity needed (peak own funding 653 M Kč instead of 1,196 M Kč).

All inputs sit on one sheet (blue = input, green = link to inputs, white = calculation); each is listed with its source and status in the source library.

## Baldwin Alexandria: the source library

A chat assistant restricted to the project's library (`docs/alexandria/knowledge.md`): every data source, what was taken from it, every model input with its source or the note *assumption*, and the formulas that connect them. It explains where a number comes from and how changing it moves the result, and declines anything outside the library. It runs on a Cloudflare Worker that calls Google Gemini; the API key is kept as a Worker secret.

---

## Repository layout

```
docs/                 the website, exactly as GitHub Pages serves it (generated by the build)
  index.html            the front page: link-preview tags, then on to the map
  map.html              Baldwin Palantir, the map
  acre/                 Baldwin Acre: the page and its read-only Excel viewer
  alexandria/           Baldwin Alexandria: the chat page, its library and the Worker code
  data/                 files the pages load: motorways, railways, the Šeberov model
  i18n.js               language switching (CS / EN / SK), shared by all three pages
src/                  the map's browser scripts, inlined into docs/index.html by the build
build/                the Python that downloads the open data and builds docs/
```

Everything in `docs/` is generated: edit `src/`, `build/` or the two source folders below, then rebuild.

| File | Responsibility |
|---|---|
| `build/make_map.py` | assembles the map: layers, styles, start screen; copies Alexandria and Acre into `docs/`; extracts the Excel template for the export |
| `build/mpp.py` | downloads the open data (IPR Praha, ČÚZK, PID), caching the last good response in `build/cache/` |
| `build/screening.py` | computes each area's land price, metro distances and flood share |
| `src/deal_popup.js` | the area panel and its live cadastral parcels |
| `src/selection.js` | multi-area and multi-parcel selection with totals |
| `src/export.js` | the Excel export to Baldwin Acre |
| `src/search.js` | search for areas, localities, metro stations and addresses (RÚIAN) |
| `src/price_filter.js` | land-price filter |
| `src/drawer.js` | filter window, layer order and language switcher |
| `src/lines.js` | motorway and railway layers with train stations |
| `src/i18n.js` | the three languages: texts, the switcher's choice, the browser's memory of it |
| `src/sky.js`, `src/lightning.js`, `src/clouds.js` | the start screen and the zoomed-out easter egg |

## Building

Requires Python 3 with `folium`, `shapely`, `openpyxl` and `requests`.

```
python build/make_map.py
```

This rebuilds everything in `docs/`. The sources of the other two parts live beside this repository and are edited there:

| Folder beside the repo | Contents |
|---|---|
| `Baldwin Alexandria/` | `index.html`, the library `knowledge.md`, the Cloudflare Worker `worker.js` |
| `Baldwin Acre/` | the model `Baldwin Acre.xlsx` and its page in `web/` |

**Stack:** Python (folium, shapely, openpyxl) · Leaflet · ExcelJS · Cloudflare Workers · Google Gemini · GitHub Pages (served from `/docs`).

## Data sources

| Provider | Data | Licence |
|---|---|---|
| IPR Praha | Metropolitní plán areas and regulations, localities, parks, flood zones, price map, transport lines | CC BY 4.0 |
| ČÚZK | cadastral parcels (INSPIRE WFS), cadastral map, RÚIAN addresses, ZABAGED rivers, motorways and railways | CC BY 4.0 |
| PID / ROPID | stops, stations and timetables (GTFS) | CC BY 4.0 |

## Limitations

- The price map is a regulated price of building land, not a transaction price; fields are often unpriced, hence the 500 m fallback.
- Several model inputs (land price, house price, discount rates, loan margins) are assumptions and are marked as such in the library; the sensitivity grids show their effect.
- Cash flows are yearly, sales are modelled as one bulk sale, and profit tax is not included.
- Distances are straight lines; owners are not collected automatically (the cadastre requires a person to look them up).
