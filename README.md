# Baldwin Palantir

Interactive deal screener for Prague land development: every development and transformation area of the Metropolitní plán, with regulated floor area (HPP), price-map land prices, metro distance, flood risk and the cadastral parcels inside, plus multi-area / multi-parcel selection for land assembly and an export into the Baldwin Acre appraisal model.

**Live map:** https://artur20papp-source.github.io/baldwin-palantir/
**Baldwin Alexandria** (ask about the sources and how they affect the calculations): https://artur20papp-source.github.io/baldwin-palantir/alexandria/

Build: `python make_map.py` (writes `index.html`).

The project has three parts, each in its own folder next to this one:

| Folder | What it is |
|---|---|
| `Baldwin Palantir` (this repo) | the map and the website |
| `Baldwin Alexandria` | the source-library chatbot: page, library (`knowledge.md`) and Cloudflare Worker code; the build copies them into `alexandria/` here, so edit them there, not here |
| `Baldwin Acre` | the Excel appraisal model; the build reads its layout for the export and copies it as the Šeberov example (`baldwin-acre-seberov.xlsx`) |

Data: © IPR Praha (CC BY) · ČÚZK (parcels, RÚIAN, ZABAGED) · PID / ROPID (CC BY).
