// Deal-sheet popup for development areas. Inlined into map.html by make_map.py;
// __MAP__, __METRO__, __ACCENT__ and __ORANGE__ are filled in there.
(function () {
  const map = __MAP__;
  const METRO = __METRO__;
  const CPX_WFS = "https://services.cuzk.cz/wfs/inspire-CPX-wfs.asp";
  const KN_PARCEL = "https://nahlizenidokn.cuzk.cz/ZobrazObjekt.aspx?typ=parcela&id=";
  const LOCALITY_PDF = "https://ppstaticcontentprod.azureedge.net/public/pmp/appdata/klz/";
  const MAX_PARCELS = 300;

  // ČÚZK land types (druh pozemku, codelist LandTypeValue); the farmland ones pay the ZPF removal fee.
  const LAND = {
    ArableGround: t("orná půda", "arable land", "orná pôda"), Garden: t("zahrada", "garden", "záhrada"),
    Orchard: t("ovocný sad", "orchard", "ovocný sad"),
    Grassland: t("trvalý travní porost", "permanent grassland", "trvalý trávny porast"),
    Vineyard: t("vinice", "vineyard", "vinica"), Hopgarden: t("chmelnice", "hop garden", "chmeľnica"),
    Forest: t("lesní pozemek", "forest land", "lesný pozemok"), WaterArea: t("vodní plocha", "water area", "vodná plocha"),
    BuiltUpArea: t("zastavěná plocha", "built-up area", "zastavaná plocha"),
    OtherArea: t("ostatní plocha", "other area", "ostatná plocha"),
  };
  const FARMLAND = new Set(["ArableGround", "Garden", "Orchard", "Grassland", "Vineyard", "Hopgarden"]);

  const num = (v) => (v === null || v === undefined || v === "–" ? "–" : Number(v).toLocaleString("cs-CZ"));
  const km = (m) => (m === null || m === undefined ? "–"
    : m < 1000 ? `${num(m)} m` : `${(m / 1000).toLocaleString("cs-CZ", { maximumFractionDigits: 1 })} km`);
  const tag = (el, name) => (el.getElementsByTagName(name)[0] || {}).textContent || "";

  // Even-odd ray casting over every ring, so holes and multipolygons work too. pt = [lon, lat].
  function inside(pt, geom) {
    const polys = geom.type === "Polygon" ? [geom.coordinates] : geom.coordinates;
    let hit = false;
    for (const poly of polys) for (const ring of poly) {
      for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
        const [xi, yi] = ring[i], [xj, yj] = ring[j];
        if ((yi > pt[1]) !== (yj > pt[1]) && pt[0] < ((xj - xi) * (pt[1] - yi)) / (yj - yi) + xi) hit = !hit;
      }
    }
    return hit;
  }

  // GML posList ("lat lon lat lon ...") -> ring of [lon, lat]
  const ring = (text) => {
    const n = text.trim().split(/\s+/).map(Number), out = [];
    for (let i = 0; i + 1 < n.length; i += 2) out.push([n[i + 1], n[i]]);
    return out;
  };

  // Overlap test: a corner of one shape lies inside the other. Parcel corners are nudged 5 % towards
  // the parcel's own reference point first, so neighbours that only share a border don't count.
  const nudged = (ringPts, ref) => ringPts.map(([x, y]) => [x + 0.05 * (ref[0] - x), y + 0.05 * (ref[1] - y)]);

  function overlap(parcelRings, ref, area) {
    const parcel = { type: "Polygon", coordinates: parcelRings };
    const areaRings = area.type === "Polygon" ? area.coordinates : area.coordinates.flat();
    return inside(ref, area)
      || nudged(parcelRings[0], ref).some((pt) => inside(pt, area))
      || areaRings.some((r) => r.some((pt) => inside(pt, parcel)));
  }

  function sheet(p, parcelsHtml) {
    const metro = p.metro_line
      ? `<span class="mdot" style="background:${METRO[p.metro_line]}"></span>${p.metro_name} (${p.metro_line}) · ${km(p.metro_m)}` : "–";
    const flood = p.flood_pct === null || p.flood_pct === undefined ? "–"
      : p.flood_pct > 0 ? `<span class="warn">${t("ano", "yes", "áno")} · ${p.flood_pct} % ${t("plochy", "of the area", "plochy")}</span>`
      : t("ne", "no", "nie");
    const priceSrc = { plocha: t("v ploše", "in the area", "v ploche"),
                       "okolí": t("okolí 500 m", "within 500 m", "okolie 500 m") }[p.price_src] || "";
    // Regulated gross floor area, Metropolitní plán čl. 96 odst. 4: HPPreg = P × Zz × Vz
    const hpp = typeof p.z_z === "number" && typeof p.v_z === "number" ? Math.round(p.area_m2 * p.z_z / 100 * p.v_z) : null;
    return `
      <div class="deal">
        <div class="code">${p.area_code}</div>
        <div class="loc">${p.locality_name}</div>
        <div class="chips"><span>${tw(p.stabilita_txt)}</span><span>${tw(p.vyuziti_txt)}</span><span>${tw(p.struktura_txt)}</span></div>
        <div class="tiles">
          <div class="tile"><b>${num(p.area_m2)}</b><small>${t("m² výměra", "m² area", "m² výmera")}</small></div>
          <div class="tile"><b>${hpp === null ? "–" : num(hpp)}</b><small>${t("m² HPP reg.", "m² GFA reg.", "m² HPP reg.")}</small></div>
          <div class="tile"><b>${p.price ? num(p.price) : "–"}</b><small>${t("Kč/m² cena", "CZK/m² price", "Kč/m² cena")}</small></div>
        </div>
        <div class="sec">${t("Cena pozemku", "Land price", "Cena pozemku")}</div>
        <div class="drow"><span>${t("Cenová mapa hl. m. Prahy", "Prague price map", "Cenová mapa hl. m. Prahy")}</span><span>${p.price ? num(p.price) + " Kč/m²" : "–"}</span></div>
        <div class="drow"><span>${t("Zdroj ceny", "Price source", "Zdroj ceny")}</span><span>${priceSrc || t("bez ceny", "no price", "bez ceny")}</span></div>
        <div class="sec">${t("Doprava", "Transport", "Doprava")}</div>
        <div class="drow"><span>${t("Nejbližší metro", "Nearest metro", "Najbližšie metro")}</span><span>${metro}</span></div>
        <div class="drow"><span>${t("Metro D (plán)", "Metro D (planned)", "Metro D (plán)")}</span><span>${km(p.metro_d_m)}</span></div>
        <div class="sec">${t("Rizika a regulace", "Risks and regulation", "Riziká a regulácia")}</div>
        <div class="drow"><span>${t("Záplavové území", "Flood zone", "Záplavové územie")}</span><span>${flood}</span></div>
        <div class="drow"><span>${t("Zmax · max. zastavění budovami", "Zmax · max. building coverage", "Zmax · max. zastavanosť budovami")}</span><span>${num(p.z_max)}${p.z_max === "–" ? "" : " %"}</span></div>
        <div class="drow"><span>${t("Zz · základní zastavění", "Zz · basic coverage", "Zz · základná zastavanosť")}</span><span>${num(p.z_z)}${p.z_z === "–" ? "" : " %"}</span></div>
        <div class="drow"><span>${t("Vz · základní podlažnost", "Vz · basic storeys", "Vz · základná podlažnosť")}</span><span>${num(p.v_z)}</span></div>
        <div class="drow"><span>${t("HPP reg. = výměra × Zz × Vz", "GFA reg. = area × Zz × Vz", "HPP reg. = výmera × Zz × Vz")}</span><span>${hpp === null ? "–" : num(hpp) + " m²"}</span></div>
        <div class="sec">${t("Parcely v ploše", "Parcels in the area", "Parcely v ploche")} <span class="note">· ${t("vlastník v katastru", "owner in the cadastre", "vlastník v katastri")} ↗</span></div>
        <div class="parcels">${parcelsHtml}</div>
        <div class="links">
          <a href="${LOCALITY_PDF}${p.lokalita}.pdf" target="_blank" rel="noopener">${t("Krycí list lokality", "Locality sheet", "Krycí list lokality")} ${p.lokalita} ↗</a>
        </div>
        <button class="acre">Export to Baldwin Acre</button>
      </div>`;
  }

  // Parcels in a lat/lon box, live from ČÚZK. Each keeps its rings and reference point ([lon, lat]).
  async function getParcels(south, west, north, east, count) {
    const crs = "urn:ogc:def:crs:EPSG::4326";
    const url = `${CPX_WFS}?service=WFS&version=2.0.0&request=GetFeature&typeNames=CPX:CadastralParcel`
      + `&count=${count}&srsName=${crs}&BBOX=${south},${west},${north},${east},${crs}`;
    const xml = new DOMParser().parseFromString(await (await fetch(url)).text(), "application/xml");
    const parcels = [];
    for (const el of xml.getElementsByTagName("cp-ext:CadastralParcel")) {
      const geom = el.getElementsByTagName("cp:geometry")[0];
      const rings = [...geom.getElementsByTagName("gml:posList")].map((pl) => ring(pl.textContent));
      const refEl = el.getElementsByTagName("cp:referencePoint")[0];
      const typeEl = el.getElementsByTagName("cp-ext:landType")[0];
      parcels.push({ label: tag(el, "cp:label"), area: Number(tag(el, "cp:areaValue")), rings,
                     ref: refEl ? ring(tag(refEl, "gml:pos"))[0] : rings[0][0],
                     type: typeEl ? typeEl.getAttribute("xlink:href").split("/").pop() : "",
                     id: el.getAttribute("gml:id").replace("CPX.", "") });
    }
    return { parcels, matched: Number(xml.documentElement.getAttribute("numberMatched")) || 0 };
  }

  // Parcels overlapping the area, largest first.
  async function fetchParcels(layer) {
    const b = layer.getBounds();
    const area = layer.feature.geometry;
    const { parcels, matched } = await getParcels(b.getSouth(), b.getWest(), b.getNorth(), b.getEast(), MAX_PARCELS);
    const rows = parcels.filter((r) => overlap(r.rings, r.ref, area)).map((r) => ({
      ...r, partial: !inside(r.ref, area) || nudged(r.rings[0], r.ref).some((pt) => !inside(pt, area)) }));
    rows.sort((a, b) => b.area - a.area);
    return { rows, matched };
  }

  function parcelsHtml({ rows, matched }) {
    if (!rows.length) return `<div class="muted">${t("V ploše není žádná parcela.", "No parcels in this area.", "V ploche nie je žiadna parcela.")}</div>`;
    const farm = rows.filter((r) => FARMLAND.has(r.type)).length;
    return `<div class="psum">${rows.length} ${t("parcel", "parcels", "parciel")} · ${t("zemědělská půda", "farmland", "poľnohospodárska pôda")} (ZPF): ${farm} ${t("z", "of", "z")} ${rows.length}`
      + (matched > MAX_PARCELS ? ` · ${t("zobrazeno prvních", "first shown:", "zobrazených prvých")} ${MAX_PARCELS}` : "") + "</div>"
      + rows.map((r, i) => `
        <div class="prow" data-i="${i}">
          <span class="pnum" title="${t("Přiblížit na mapě", "Zoom to it", "Priblížiť na mape")}">${r.label}${r.partial
            ? `<em title="${t("Parcela přesahuje hranici plochy", "The parcel crosses the area's border", "Parcela presahuje hranicu plochy")}">${t("část", "part", "časť")}</em>` : ""}</span>
          <span>${num(r.area)} m²</span>
          <span class="ptype">${LAND[r.type] || r.type}${FARMLAND.has(r.type) ? ' <i>ZPF</i>' : ""}</span>
          <a href="${KN_PARCEL}${r.id}" target="_blank" rel="noopener">${t("Vlastník", "Owner", "Vlastník")} ↗</a>
        </div>`).join("");
  }

  // Parcel outlines on the map: farmland tinted orange, partial parcels dashed.
  // drawn as SVG, not on the map's canvas: a canvas in a pane of its own would cover the whole map and take
  // every click, while SVG lets clicks pass between its shapes to the map below
  map.createPane("selected-parcels").style.zIndex = 460;
  const parcelRenderer = L.svg({ pane: "selected-parcels" });
  const baseStyle = (r) => ({
    pane: "selected-parcels", renderer: parcelRenderer, color: "#ffffff", weight: 1.2, opacity: 0.9, dashArray: r.partial ? "4 4" : null,
    fillColor: FARMLAND.has(r.type) ? __ORANGE__ : "#ffffff", fillOpacity: FARMLAND.has(r.type) ? 0.22 : 0.06,
  });
  const hotStyle = { color: __ACCENT__, weight: 2.5, fillOpacity: 0.45 };

  function drawParcels(rows) {
    const shapes = rows.map((r) => L.polygon(r.rings.map((rg) => rg.map(([lon, lat]) => [lat, lon])), baseStyle(r))
      .bindTooltip(`${r.label} · ${num(r.area)} m² · ${LAND[r.type] || r.type}`, { sticky: true }));
    const group = L.featureGroup(shapes).addTo(map);
    const rowEl = (i) => panel.querySelector(`.prow[data-i="${i}"]`);
    const hot = (i, on) => {
      shapes[i].setStyle(on ? hotStyle : baseStyle(rows[i]));
      if (on) shapes[i].bringToFront();
      const el = rowEl(i);
      if (el) el.classList.toggle("hot", on);
    };
    shapes.forEach((s, i) => {
      s.on("mouseover", () => { hot(i, true); const el = rowEl(i); if (el) el.scrollIntoView({ block: "nearest" }); });
      s.on("mouseout", () => hot(i, false));
      // don't reopen the area panel; in parcel selection the click goes on to the map, which selects it
      s.on("click", (e) => { if (!window.baldwinSelectMode) L.DomEvent.stopPropagation(e); });
    });
    // rows -> map: hover highlights, clicking the number zooms to the parcel
    for (const el of panel.querySelectorAll(".prow")) {
      const i = Number(el.dataset.i);
      el.addEventListener("mouseenter", () => hot(i, true));
      el.addEventListener("mouseleave", () => hot(i, false));
      el.querySelector(".pnum").addEventListener("click", () => map.fitBounds(shapes[i].getBounds(), fit()));
    }
    return group;
  }

  // Side panel instead of a popup, so the area and its parcels stay visible next to it.
  const panel = document.createElement("aside");
  panel.className = "ds-panel";
  document.body.appendChild(panel);
  // keep the area clear of the panel: beside it on a desktop (and of the filter window too when that is open,
  // the panel then sitting to its right), above the bottom sheet on a phone
  const phone = window.matchMedia("(max-width: 700px)");
  const fit = () => phone.matches
    ? { paddingTopLeft: [20, 130], paddingBottomRight: [20, Math.round(window.innerHeight * 0.62) + 20], maxZoom: 18 }
    : { paddingTopLeft: [430 + (document.body.classList.contains("drawer-open") ? 328 : 0), 60],
        paddingBottomRight: [40, 40], maxZoom: 18 };
  let current = null;  // { layer, parcels } of the open area

  function close() {
    if (!current) return;
    if (current.parcels) map.removeLayer(current.parcels);
    current.layer.setStyle({ weight: 0.6 });
    current = null;
    panel.classList.remove("open");
  }

  function render(p, parcelsBody) {
    panel.innerHTML = `<button class="ds-close" title="${t("Zavřít", "Close", "Zavrieť")}">×</button>` + sheet(p, parcelsBody);
    panel.querySelector(".ds-close").addEventListener("click", close);
    panel.querySelector(".acre").addEventListener("click", (e) => exportAcre(p, e.currentTarget));
  }

  // The open area as the site of an appraisal in the Baldwin Acre model; the farmland (ZPF) share is
  // known once its parcels have loaded.
  async function exportAcre(p, button) {
    // ZPF: the farmland share of its parcels applied to the area itself (parcels that reach beyond the
    // area's edge would otherwise count at their full size)
    const rows = (current && current.rows) || null;
    const m2 = (list) => list.reduce((s, r) => s + r.area, 0);
    const zpf = rows && m2(rows) ? p.area_m2 * m2(rows.filter((r) => FARMLAND.has(r.type))) / m2(rows) : null;
    const label = `${p.area_code} ${p.locality_name}`;
    button.disabled = true;
    button.textContent = t("Připravuji…", "Preparing…", "Pripravujem…");
    try {
      await window.baldwinExportAcre({ siteArea: p.area_m2, zpfM2: zpf, price: p.price || null, label,
                                       zz: typeof p.z_z === "number" ? p.z_z : null, codes: [p.area_code],
                                       file: label.replace(/[\\/:*?"<>|]+/g, "-"), date: new Date().toLocaleDateString("cs-CZ") });
    } catch (err) { alert(t("Export se nepovedl: ", "Export failed: ", "Export sa nepodaril: ") + err.message); }
    button.disabled = false;
    button.textContent = "Export to Baldwin Acre";
  }

  async function open(layer) {
    close();
    // on a phone both are sheets at the bottom, so an opened area closes the filter window there
    if (phone.matches && window.baldwinCloseDrawer) window.baldwinCloseDrawer();
    const p = layer.feature.properties;
    const mine = (current = { layer, parcels: null });
    layer.setStyle({ weight: 2.5 });
    render(p, `<div class="muted">${t("Načítám z katastru…", "Loading from the cadastre…", "Načítavam z katastra…")}</div>`);
    panel.classList.add("open");
    panel.scrollTop = 0;
    map.flyToBounds(layer.getBounds(), { ...fit(), duration: 0.9 });
    let result;
    try {
      result = await fetchParcels(layer);
    } catch (err) {
      if (current === mine) render(p, `<div class="muted">${t("Katastr teď neodpovídá, zkuste to znovu.", "The cadastre isn't responding, try again.", "Kataster teraz neodpovedá, skúste to znova.")}</div>`);
      return;
    }
    if (current !== mine) return;  // another area was opened, or the panel closed, while loading
    render(p, parcelsHtml(result));
    mine.parcels = drawParcels(result.rows);
    mine.rows = result.rows;  // for the export
  }

  document.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
  window.baldwinOpenArea = open;  // used by the search box
  window.baldwinClosePanel = close;  // used by the filter window on a phone, which closes the panel when it opens
  window.baldwinCadastre = { getParcels, inside, LAND, FARMLAND, KN_PARCEL };  // used by the selection

  // Every folium GeoJson is a global geo_json_*; bind the areas (they carry an area_code).
  for (const key of Object.keys(window)) {
    if (!key.startsWith("geo_json_") || !window[key].eachLayer) continue;
    window[key].eachLayer((layer) => {
      if (layer.feature && layer.feature.properties && layer.feature.properties.area_code) {
        layer.on("click", () => { if (!window.baldwinSelectMode) open(layer); });  // selecting: selection.js
      }
    });
  }
})();
