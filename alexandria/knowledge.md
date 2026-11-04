# Baldwin Alexandria: the source library of Baldwin Palantir and Baldwin Acre

This file is the only thing Baldwin Alexandria may answer from. It lists every source used in the
project, what was taken from it, and how it moves the calculations. Values marked **assumption** have
no external source; values marked **verify** come from a source that may have changed since.

The project has two parts:

- **Baldwin Palantir**: an interactive map of Prague's development and transformation areas
  (https://artur20papp-source.github.io/baldwin/). For each area it shows size, regulated
  floor area (HPP), an official land price, metro access, flood risk and the cadastral parcels inside.
- **Baldwin Acre**: an Excel development appraisal with four calculation sheets: selling serviced plots
  (Analysis), the same with a land loan (Analysis (Loan)), building and selling houses (Analysis H), and
  houses financed with a land loan and a construction loan (Analysis H (Loan)). Its worked example is area 414/267/5033 in
  Šeberov. The map's "Export to Baldwin Acre" button writes the model as a template with the map's
  facts filled in (for Šeberov it hands out the filled model itself).

---

## Part A: data sources of the map (Baldwin Palantir)

### A1. Metropolitní plán Praha: development and transformation areas
- **Source:** IPR Praha (Institut plánování a rozvoje hl. m. Prahy), open data, layer
  `MPP_CUR_MPP_400_POTENCIAL_P` (transformační a rozvojové plochy) at
  https://mp.iprpraha.cz/arcgis/rest/services/Hosted. Licence CC BY 4.0, credit "datový podklad © IPR Praha".
- **What it gives:** the outline of every area (1,144 residential ones are shown: rozvojové = green,
  transformační = brown), its code (kapitola/lokalita/id, e.g. 414/267/5033), stability, use,
  structure, and the regulations **Zmax**, **Zz** and **Vz**.
- **Area (výměra):** measured by us from the outline in the Czech national grid S-JTSK (EPSG:5514), in
  m². Web-map coordinates would overstate areas about 2.4× in Prague, so S-JTSK is used for all areas
  and distances.
- **Effect on calculations:** výměra is the **Site area** of the appraisal (Baldwin Acre Inputs C7),
  which drives the number of plots, the land price, revenue and every result. Zz feeds the export's
  **Max house footprint** (Inputs C11). Zz × Vz gives HPP reg. (A2).

### A2. Metropolitní plán regulations: Zz, Vz, Zmax and HPP reg.
- **Source:** the Metropolitní plán's text (IPR Praha). **Zz** = základní zastavěnost, the basic building
  coverage in % of the area (čl. 95). **Vz** = základní podlažnost, the basic number of floors.
  **Zmax** = the maximum building coverage.
- **Formula used:** regulated gross floor area **HPP reg. = výměra × Zz × Vz** (Metropolitní plán
  čl. 96 odst. 4). Example Šeberov 414/267/5033: 89,916 m² × 20 % × 2 = 35,966 m².
- **Effect:** HPP shows how much floor area the plan allows; in the model the closest input is
  Max house footprint (Zz), and the municipality contribution is charged per m² of floor area.
  Areas without set Zz/Vz show "–" and get no HPP.

### A3. Cenová mapa (official price map of Prague)
- **Source:** IPR Praha open data, layer `SED_CUR_SED_CENOVAMAPA_P` (cenová mapa stavebních pozemků
  hl. m. Prahy), CC BY. The city's official price per m² of building land, zone by zone.
- **How it is used:** each area's price is the **area-weighted average** of the priced zones inside it
  ("v ploše"). If no priced zone is inside (often the case for fields, which the map does not price),
  the zones within **500 m** are used instead ("okolí 500 m"). Areas with neither show no price.
  Example Šeberov 414/267/5033: 16,670 Kč/m² (in the area).
- **Effect on calculations:** the export puts it into **Sell price (incl. VAT)** (Inputs C16), the price
  serviced plots sell for. Revenue = plot area × sell price, so it moves revenue, VAT, selling costs,
  profit and IRR directly. The land purchase price is a separate input (Inputs C17, 5,950 Kč/m²), so
  the sell price no longer moves the land cost. It is a regulated price of building land, not a
  transaction price.
- **Also used in the map:** the price filter and the value estimates in the selection window
  (výměra × price).

### A4. Flood zones (záplavová území)
- **Source:** IPR Praha, Metropolitní plán layer `MPP_CUR_MPP_700_TI_ZAPLAVUZ_P`, CC BY.
- **How it is used:** the share of each area lying in a flood zone (% of its area), shown as a risk.
- **Effect:** a screening flag only; it does not enter the appraisal numbers.

### A5. Localities, parks, water, transport lines (map background)
- **Source:** IPR Praha open data, CC BY: localities `MPP_CUR_MPP_300_LOKALITY_P` (neighbourhood names
  and the city outline), parks `MPP_CUR_MPP_100_PARKY_P`, water surfaces
  `AGD_CUR_AGD_OCH_VODNIPLOCHYTOKY_P`, existing transport lines `MPP_CUR_MPP_STAV_600_DI_TRASY_L`
  (metro = kapitola 621, tram = 622) and planned lines `MPP_CUR_MPP_600_DI_TRASY_L` (Metro D, stav 2).
- **Effect:** background and context; the planned Metro D line gives each area its distance to Metro D.
  No effect on the appraisal.

### A6. River surfaces (Vltava) from ZABAGED
- **Source:** ČÚZK ZABAGED (Základní báze geografických dat), layer "Vodní plocha" (flowing water,
  stojvoda = N), https://ags.cuzk.cz/arcgis/rest/services/ZABAGED_POLOHOPIS/MapServer/132, open data CC BY 4.0.
- **How it is used:** the map draws only the Vltava, taken as the biggest connected piece of ZABAGED's
  river surfaces in Prague (95 % of their area); small streams and ponds are left out. Visual only.

### A6b. Motorways and railways in Prague (ZABAGED)
- **Source:** ČÚZK ZABAGED, layers "Silnice, dálnice" (only motorways: dálnice I. and II. třídy, incl. the
  Prague ring road D0; ramps left out) https://ags.cuzk.cz/arcgis/rest/services/ZABAGED_POLOHOPIS/MapServer/79
  and "Železniční trať" .../MapServer/75, open data CC BY 4.0, cut to Prague's city limits.
- **How it is used:** two switches in the filter window, Motorways (grey, ~78 km) and Railways (pink,
  ~218 km), to show which areas lie close to them. The Railways switch also shows Prague's 42 train
  stations from PID's stop list (A7), as small dots named with their lines on hover, from zoom 12.
- **Effect:** context only; not an input of the appraisal.

### A7. Public transport: PID stops, metro stations, bus routes
- **Source:** PID / ROPID open data, CC BY: stops https://data.pid.cz/stops/json/stops.json and the
  timetable feed https://data.pid.cz/PID_GTFS.zip (bus route shapes).
- **How it is used:** the nearest metro station to each area (straight-line distance in S-JTSK from the
  area outline), its line (A/B/C), the distance to the planned Metro D, and the tram/bus layers.
- **Effect:** a location-quality indicator shown with each area; not an input of the appraisal.

### A8. Cadastre: parcels, land types, owners (ČÚZK)
- **Sources:** ČÚZK INSPIRE cadastral parcels WFS https://services.cuzk.cz/wfs/inspire-CPX-wfs.asp
  (parcel outline, number, area, land type), the cadastral map WMS https://services.cuzk.cz/wms/wms.asp
  (parcel borders from zoom 17), and Nahlížení do katastru nemovitostí
  https://nahlizenidokn.cuzk.cz (owner and title, opened per parcel; not automated).
- **How it is used:** the parcels overlapping an area are listed with their area and land type; a
  parcel counts as farmland (**ZPF**, zemědělský půdní fond) if its land type is arable land, garden,
  orchard, permanent grassland, vineyard or hop garden. Parcels reaching beyond the area are marked "část".
- **Effect on calculations:** the ZPF share tells whether the **ZPF removal fee** (Part B) applies. The
  export notes it beside the site area: ZPF ≈ (farmland parcels' area ÷ all parcels' area) × výměra
  (Šeberov ≈ 91 %). In the selection window, picked parcels can replace the area as the site
  (site area = sum of the parcels).

### A9. Addresses (RÚIAN)
- **Source:** ČÚZK RÚIAN search service (suggest + findAddressCandidates). Used only by the search box.
- **Effect:** none on calculations.

### A10. Locality cover sheets (krycí listy lokalit)
- **Source:** the Metropolitní plán's PDF per locality (linked from each area's panel).
- **Effect:** reading material; not machine-read.

---

## Part B: inputs of the appraisal model (Baldwin Acre) and their sources

Values are the Šeberov worked example (area 414/267/5033). Cell = Inputs sheet.

| Input | Value | Source | Status |
|---|---|---|---|
| Site area (C7) | 89,915 m² | Metropolitní plán area 414/267/5033 (Šeberov), measured | sourced |
| Usable share of site (C8) | 70 % | the rest is roads and green areas | assumption |
| Plot size (C9) | 700 m² | typical Prague family-house plot | assumption |
| Max house footprint (C11) | 35 % of plot | design choice; the map's export uses the plan's Zz instead (20 % in Šeberov) | assumption |
| Sell price incl. VAT (C16) | 17,000 Kč/m² | Prague price map (16,670 Kč/m² in the area) and Sreality listings; MAX Reality puts the average Prague plot at ~20,400 Kč/m² (June 2026) | sourced, verify |
| Land price (C17) | 5,950 Kč/m² of site | fixed purchase price; set at 35 % of the 17,000 Kč/m² plot price as a rule of thumb (20–35 %) | **assumption** |
| Purchase costs (C18) | 1 % of land price | | assumption |
| Infrastructure (C21) | 1,100 Kč per m² of plot | zasitovanipozemku.cz ("průměrně cca 1 100 Kč/m²" for a whole development; it does not say clearly whether per m² of plot or of site); cross-checked with banky.cz mains costs and a ČVUT thesis on servicing costs | sourced, verify |
| ZPF coefficient (C22) | 11 | zákon č. 334/1992 Sb. (farmland protection), annex: coefficient for soil protection class I; Šeberov's soil assumed class I | sourced (class assumed) |
| ZPF base rate (C23) | 15 Kč/m² | base price of the soil from its BPEJ code (estimate for top soils); exact value needs the parcel's BPEJ from the cadastre; ecological weight taken as 1 | estimate |
| Municipality contribution (C24) | 700 Kč per m² of floor area | Prague's investor contribution methodology (Metodika spoluúčasti investorů, praha.eu): 700 Kč/m² of new HPP when no plan change is needed (2,300 Kč/m² with a change) | sourced, verify (2021–22 figures; districts may have own rules) |
| Permits & planning (C25) | 5 % of infrastructure | ČVUT thesis (Trnovská 2019): 4.4–7.7 %; UNIKA fee scale | sourced |
| Contingency (C26) | 10 % of infrastructure | industry convention | assumption |
| Surveys (C27) | 1 % of infrastructure | | assumption |
| Holding costs per period (C28) | 18,000 Kč | property tax on farmland while permitting: area × ~15 Kč × 1.35 % (zákon č. 338/1992 Sb.; finance.cz, banky.cz) | sourced |
| Holding periods (C29) | 3 | years of permitting | assumption |
| Development management fee (C30) | 5 % of dev. subtotal | | assumption |
| Selling costs (C33) | 3 % of net revenue | agent / marketing | assumption |
| VAT on plots (C34) | 21 % | standard Czech VAT on building plots (zákon č. 235/2004 Sb.) | sourced |
| Discount rate (C37) | 12 % p.a. | required return of an unlevered project; set to 12 % so NPV is meaningful | assumption |
| Discount rate with loan (C38) | 15 % p.a. | required return on equity | assumption |
| Living area share (C51) | 85 % of floor plan | | assumption |
| House sale price incl. VAT (C52) | 115,000 Kč/m² living area | | assumption (no source recorded) |
| VAT on houses (C53) | 12 % | reduced rate for social housing: family houses with floor area up to 350 m² (zákon č. 235/2004 Sb.) | sourced, verify |
| Build cost excl. VAT (C54) | 50,000 Kč/m² living area | RTS cost indicators (brick family house 2026: 10,410 Kč/m³, via dozor-brno.cz; ČKAIT: +14 % in 2025) ≈ 50,000 Kč/m² for a ~245 m² bungalow; cross-checked with catalogue bungalows (ceskestavby.cz, ~40,000–47,000 Kč/m²) | sourced |
| House design & permits (C55) | 3 % of build cost | ČVUT thesis 4.4–7.7 % for a one-off design, lower for 89 identical houses | sourced + assumption |
| House connections (C56) | 150,000 Kč/house | water and sewer ~50k each (banky.cz) + power 25 A × 500 Kč (vyhláška č. 16/2016 Sb.) ≈ 115k, rounded up | sourced, rounded |
| House contingency / overhead / selling (C57–C59) | 5 % / 5 % / 3 % | | assumption |
| Property tax base rate (C62) | 3.50 Kč/m² | building land, zákon č. 338/1992 Sb. | sourced |
| Prague coefficient (C63, "Šeberov coefficient") | 4.5 (from 2026) | zákon č. 338/1992 Sb. | sourced, verify |
| Local coefficient (C64) | 2 | Prague's local coefficient; check on financnisprava.cz | verify |
| Loan as % of land price (Loan C36) | 60 % | banks lend roughly 50–70 %; on land without a building permit 50 % is more usual | assumption |
| 3M PRIBOR (Loan C38) | 3.94 % | ČNB fixing of 21. 10. 2026 (cnb.cz) | sourced, dated |
| Land loan spread over PRIBOR (Loan C39) | 4 % | ≈ 1.6 % market base (ČNB: average rate on new loans over 30 mil. Kč to firms 5.53 % in September 2026, minus 3M PRIBOR 3.94 %) + ≈ 2.4 % premium for unpermitted land, the riskiest collateral; no published Czech figure for the premium | base sourced, premium **assumption** |
| Construction loan LTC (H Loan C51) | 60 % of each year's Phase 2 costs | drawn step by step against verified construction progress (Czech banks finance "prostavěnost": arws.cz, hyponamiru.cz) | practice sourced, share assumption |
| Construction loan spread (H Loan C54) | 2.5 % | ≈ 1.6 % ČNB market base (as above) + ≈ 1 % development premium; lower than the land loan because a permit exists and money is released only against built work | base sourced, premium **assumption** |
| Arrangement fee (H Loan C56) | 0 % | no bank offer to quote yet | assumption |
| Timing (C40–C48, C67–C70) | land year 0, permits & surveys year 1, infrastructure/ZPF/contingency/fee year 2, sale of plots year 4; houses designed year 3, built years 4–5, sold year 5 | year 3 is a permitting delay; all houses are sold in one bulk sale to an investment fund in year 5 (funds buying in bulk usually expect a discount on the price per m²) | assumption |

---

## Part C: how the inputs move the results (formulas of Baldwin Acre)

**Land subdivision (sheet Analysis), Šeberov results in brackets:**
- Number of plots = ROUNDDOWN(site area × usable share ÷ plot size) (89 plots)
- Plot area sold = plots × plot size (62,300 m²)
- Land price per m² = Inputs C17 (5,950 Kč/m², a fixed input); land price = that × **site area** (≈ 535 M Kč)
- Infrastructure = plot area × 1,100 (68.5 M); ZPF levy = plot area × coefficient × base rate (10.3 M)
- Permits, contingency, surveys = % of infrastructure; management fee = % of the development subtotal;
  holding = per period × periods
- Revenue = plot area × sell price; VAT = revenue × 21/121; selling costs = 3 % of net revenue
- Profit = net sale proceeds − total cost (214.4 M; margin 24.5 %; profit on cost 33.8 %)
- Cash flows by year → **IRR 8.1 %**, **NPV at 12 % = −76.4 M Kč**: profitable, but below the return an
  investor would require. Land is ~85 % of total cost, so the land price and the sell price are the
  inputs that matter most; they are separate inputs and are tested separately.
- The sensitivity grid shows IRR for sell prices 15,000 / 17,000 / 19,000 Kč/m² against land prices
  4,500 / 5,950 / 7,500 Kč/m².

**With a bank loan (sheet Analysis (Loan)):** loan = 60 % of the land price, interest = 3M PRIBOR + 4 %
(7.94 %), repaid at the sale. Results: profit 112.4 M, equity IRR 8.3 %, NPV at 15 % = −62.0 M,
peak equity 390 M (vs 635 M without a loan). The IRR sensitivity table varies the loan share
(50/60/70 %) and the spread (3/4/5 %).

**Phase 2, building houses (sheet Analysis H):** floor plan = plot × footprint (245 m²), living
area = 85 % (208 m²), sale at 115,000 Kč/m² incl. 12 % VAT, build cost 50,000 Kč/m², plus design,
connections, contingency, overhead, the municipality contribution (700 Kč/m² of floor area) and
property tax. Results: profit 131.6 M, IRR 3.5 %, 82.8 M less profit than selling the plots. Its
sensitivity grid shows IRR for house sale prices 105,000 / 115,000 / 125,000 Kč/m² against build costs
45,000 / 50,000 / 55,000 Kč/m².

**Houses with both loans (sheet Analysis H (Loan)):** one cash flow table, Value | Change (vs. Analysis H) | Unit.
- **Land loan:** taken from Analysis (Loan): 60 % of the land price (321.0 M) drawn in year 0, interest
  3.94 % + 4 % = 7.94 % paid every year (25.5 M a year), repaid in **year 5 from the house sales** (not
  in the plot-sale year, since no plots are sold). Total land-loan interest 127.4 M.
- **Construction loan:** each year the bank pays 60 % of that year's Phase 2 costs (25.8 M in year 3,
  311.0 M in years 4 and 5; 647.8 M in total). Interest = 6.44 % × (everything drawn in earlier years +
  half of this year's drawdown, because money arrives through the year), paid every year (0.8 M, 11.7 M,
  31.7 M; 44.2 M in total). The whole amount is repaid in year 5 from the sales. Interest is paid, not
  added to the debt, so there is no interest on interest.
- **Results:** total cost 1,886.0 M incl. 171.7 M of financing costs; profit **−40.1 M**, IRR **−2.2 %**,
  NPV at 15 % −196.4 M, equity multiple 0.94x, peak own money 652.7 M (vs 1,196.1 M without loans).
- **Why it loses money (negative leverage):** the houses earn about 3.5 % a year without loans, while the
  loans cost 6.44–7.94 %. Borrowing at a rate above the project's return lowers the result with every
  crown borrowed; the loans only reduce how much own money is needed. The sensitivity grid (LTC 50/60/70 %
  across, construction spread 1.5/2.5/3.5 % down) is negative everywhere and worse with more debt
  (from −1.4 % at 50 % / 1.5 % to −3.2 % at 70 % / 3.5 %). The project needs a return above about 6.5 %
  before the construction loan starts to help.

**What the map changes when exporting:** site area (výměra) → Inputs C7; Zz → Max house footprint C11;
price map → Sell price C16 (area-weighted when several areas are picked); ZPF share as a note. All other
inputs stay empty, because they are assumptions about the project, not facts about the place.

---

## Part D: known limits
- The price map is a regulated price of building land; fields are often unpriced, hence the 500 m fallback.
- The land price (5,950 Kč/m², set as 35 % of the plot price) is the weakest assumption and dominates the result.
- ZPF base rate and coefficient are estimates until the parcels' BPEJ codes are read from the cadastre.
- Distances are straight lines, not walking routes.
- Owner names are not collected automatically (the cadastre requires a person to look them up).
- Yearly cash flows; all plots (year 4) or all houses (year 5, bulk sale to a fund) are sold in one year; no profit tax.
- With gradual sales a bank would take a release price per house sold (often 110–120 % of that house's share of the loan), so the loan would be repaid before the last houses sell; the model does not need this while the sale is one bulk deal.
- The loan spreads' premiums over the ČNB market base are assumptions; the sensitivity grids show their effect.
- Sources marked "verify" may have changed (contribution methodology 2021–22, tax coefficients, PRIBOR date).
