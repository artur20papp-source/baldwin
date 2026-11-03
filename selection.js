// Selection of several development areas and/or cadastral parcels (land assembly), with their totals
// in a window at the bottom right. Inlined into map.html by make_map.py after deal_popup.js;
// __MAP__ and __PURPLE__ are filled in there.
(function () {
  const map = __MAP__;
  const PURPLE = __PURPLE__;
  const PARCEL_ZOOM = 17;  // the cadastral map draws parcel borders only from here
  const cad = window.baldwinCadastre;

  const num = (v) => Math.round(v).toLocaleString("cs-CZ");
  const mil = (kc) => `${(kc / 1e6).toLocaleString("cs-CZ", { maximumFractionDigits: 1 })} mil. Kč`;
  const sum = (list, f) => list.reduce((s, x) => s + (f(x) || 0), 0);
  // Regulated gross floor area, Metropolitní plán čl. 96 odst. 4: HPPreg = P × Zz × Vz
  const hpp = (p) => (typeof p.z_z === "number" && typeof p.v_z === "number" ? p.area_m2 * p.z_z / 100 * p.v_z : 0);

  const areaLayers = [];
  for (const key of Object.keys(window)) {
    if (!key.startsWith("geo_json_") || !window[key].eachLayer) continue;
    window[key].eachLayer((l) => { if (l.feature && l.feature.properties && l.feature.properties.area_code) areaLayers.push(l); });
  }

  map.createPane("selection").style.zIndex = 465;
  const areas = new Map();    // area_code -> { layer, outline }
  const parcels = new Map();  // parcel id -> { r, shape, price }
  let mode = null;            // null, "areas" or "parcels"

  function toggleArea(layer) {
    const code = layer.feature.properties.area_code;
    if (areas.has(code)) {
      map.removeLayer(areas.get(code).outline);
      areas.delete(code);
    } else {
      const outline = L.geoJSON(layer.feature, { pane: "selection", interactive: false,
        style: { color: PURPLE, weight: 2.5, fillColor: PURPLE, fillOpacity: 0.5 } }).addTo(map);
      areas.set(code, { layer, outline });
    }
    render();
  }

  // A parcel's price: the price-map price of the development area its reference point lies in.
  function priceAt(ref) {
    const ll = L.latLng(ref[1], ref[0]);
    for (const l of areaLayers) {
      if (l.getBounds().contains(ll) && cad.inside(ref, l.feature.geometry)) return l.feature.properties.price || null;
    }
    return null;
  }

  function toggleParcel(r) {
    if (parcels.has(r.id)) {
      map.removeLayer(parcels.get(r.id).shape);
      parcels.delete(r.id);
    } else {
      const shape = L.polygon(r.rings.map((rg) => rg.map(([lon, lat]) => [lat, lon])), { pane: "selection",
        interactive: false, color: PURPLE, weight: 2, fillColor: PURPLE, fillOpacity: 0.35 }).addTo(map);
      parcels.set(r.id, { r, shape, price: priceAt(r.ref) });
    }
    render();
  }

  function clear() {
    for (const a of areas.values()) map.removeLayer(a.outline);
    for (const p of parcels.values()) map.removeLayer(p.shape);
    areas.clear();
    parcels.clear();
    render();
  }

  // ---- window
  const el = L.DomUtil.create("div", "ds-select");
  el.innerHTML = `<div class="sh"><span class="ft">Výběr</span><div class="seg">
      <button data-m="areas" title="Vybírat zelené a hnědé plochy">Plochy</button>
      <button data-m="parcels" title="Vybírat parcely z katastru">Parcely</button></div></div>
    <div class="sbody deal"></div>`;
  const body = el.querySelector(".sbody");
  L.DomEvent.disableClickPropagation(el);
  L.DomEvent.disableScrollPropagation(el);
  new (L.Control.extend({ options: { position: "bottomright" }, onAdd: () => el }))().addTo(map);

  function setMode(m) {
    mode = window.baldwinSelectMode = m;
    for (const b of el.querySelectorAll(".seg button")) b.classList.toggle("on", b.dataset.m === m);
    map.getContainer().classList.toggle("selecting", !!m);
    render();
  }
  el.querySelector(".seg").addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (b) setMode(mode === b.dataset.m ? null : b.dataset.m);
  });

  function render(note) {
    const A = [...areas.values()].map((a) => a.layer.feature.properties);
    const P = [...parcels.values()];
    let h = note ? `<div class="hint">${note}</div>` : "";
    if (!A.length && !P.length && mode) {
      h += `<div class="hint">${mode === "areas" ? "Klikněte na zelené nebo hnědé plochy."
        : `Klikněte na parcely v mapě${map.getZoom() < PARCEL_ZOOM ? " (první klik přiblíží mapu)" : ""}.`}</div>`;
    } else if (!A.length && !P.length) {
      // nothing picked yet: what the selection is for
      h += `<div class="hint explain">Klikáním v mapě poskládejte pozemek z ploch nebo parcel a pošlete ho do <b>Baldwin Acre</b>.</div>`;
    }
    if (A.length) {
      const priced = A.filter((p) => p.price);
      const value = sum(priced, (p) => p.area_m2 * p.price);
      const pricedM2 = sum(priced, (p) => p.area_m2);
      h += `<div class="sec">Plochy · ${A.length}</div>
        <div class="tiles">
          <div class="tile"><b>${num(sum(A, (p) => p.area_m2))}</b><small>m² výměra</small></div>
          <div class="tile"><b>${num(sum(A, hpp))}</b><small>m² HPP reg.</small></div>
          <div class="tile"><b>${pricedM2 ? num(value / pricedM2) : "–"}</b><small>Kč/m² průměr</small></div>
        </div>
        <div class="drow"><span>Hodnota dle cenové mapy</span><span>${priced.length ? mil(value) : "–"}</span></div>
        ${priced.length < A.length ? `<div class="drow"><span>Bez ceny</span><span>${A.length - priced.length} z ${A.length}</span></div>` : ""}
        ${A.map((p) => `<div class="srow"><span class="sname" data-a="${p.area_code}" title="Otevřít">${p.area_code}</span>
          <span>${num(p.area_m2)} m²</span><button class="x" data-a="${p.area_code}" title="Odebrat">×</button></div>`).join("")}`;
    }
    if (P.length) {
      const farm = P.filter((p) => cad.FARMLAND.has(p.r.type));
      const priced = P.filter((p) => p.price);
      const value = sum(priced, (p) => p.r.area * p.price);
      const types = {};
      for (const p of P) types[p.r.type] = (types[p.r.type] || 0) + p.r.area;
      h += `<div class="sec">Parcely · ${P.length}</div>
        <div class="tiles">
          <div class="tile"><b>${num(sum(P, (p) => p.r.area))}</b><small>m² výměra</small></div>
          <div class="tile"><b>${num(sum(farm, (p) => p.r.area))}</b><small>m² ZPF</small></div>
          <div class="tile"><b>${priced.length ? mil(value).replace(" mil. Kč", "") : "–"}</b><small>mil. Kč odhad</small></div>
        </div>
        ${Object.entries(types).sort((a, b) => b[1] - a[1]).map(([t, m2]) =>
          `<div class="drow"><span>${cad.LAND[t] || t}</span><span>${num(m2)} m²</span></div>`).join("")}
        ${priced.length < P.length ? `<div class="drow"><span>Mimo plochy s cenou</span><span>${P.length - priced.length} z ${P.length}</span></div>` : ""}
        ${P.map(({ r }) => `<div class="srow p"><span class="sname" data-p="${r.id}" title="Přiblížit">${r.label}</span>
          <span>${num(r.area)} m²</span><a href="${cad.KN_PARCEL}${r.id}" target="_blank" rel="noopener">Vlastník ↗</a>
          <button class="x" data-p="${r.id}" title="Odebrat">×</button></div>`).join("")}`;
    }
    if (A.length || P.length) h += '<button class="acre">Export to Baldwin Acre</button><button class="clear">Vymazat výběr</button>';
    body.innerHTML = h;
  }

  // The selection as the site of an appraisal in the Baldwin Acre model: the parcels if any are picked
  // (they are the land actually bought), otherwise the areas.
  async function exportAcre(button) {
    const A = [...areas.values()].map((a) => a.layer.feature.properties);
    const P = [...parcels.values()];
    const weighted = (list, m2, price) => {
      const priced = list.filter(price);
      const m = sum(priced, m2);
      return m ? sum(priced, (x) => m2(x) * price(x)) / m : null;
    };
    const short = (list) => list.slice(0, 3).join(", ") + (list.length > 3 ? ` +${list.length - 3}` : "");
    const zz = (p) => (typeof p.z_z === "number" ? p.z_z : 0);
    const d = P.length
      ? { siteArea: sum(P, (p) => p.r.area), zpfM2: sum(P.filter((p) => cad.FARMLAND.has(p.r.type)), (p) => p.r.area),
          price: weighted(P, (p) => p.r.area, (p) => p.price), zz: null,
          priceMixed: new Set(P.map((p) => p.price)).size > 1, label: `parcely ${short(P.map((p) => p.r.label))}` }
      : { siteArea: sum(A, (p) => p.area_m2), zpfM2: null,
          price: weighted(A, (p) => p.area_m2, (p) => p.price), zz: weighted(A, (p) => p.area_m2, zz),
          priceMixed: new Set(A.map((p) => p.price)).size > 1, zzMixed: new Set(A.map(zz)).size > 1,
          label: `plochy ${short(A.map((p) => p.area_code))}`, codes: A.map((p) => p.area_code) };
    d.file = d.label.replace(/[\\/:*?"<>|]+/g, "-");
    d.date = new Date().toLocaleDateString("cs-CZ");
    button.disabled = true;
    button.textContent = "Připravuji…";
    try { await window.baldwinExportAcre(d); } catch (err) { alert("Export se nepovedl: " + err.message); }
    button.disabled = false;
    button.textContent = "Export to Baldwin Acre";
  }

  body.addEventListener("click", (e) => {
    const t = e.target;
    if (t.classList.contains("clear")) return clear();
    if (t.classList.contains("acre")) return exportAcre(t);
    if (t.classList.contains("x")) {
      if (t.dataset.a) toggleArea(areas.get(t.dataset.a).layer);
      else toggleParcel(parcels.get(t.dataset.p).r);
    } else if (t.classList.contains("sname")) {
      if (t.dataset.a) window.baldwinOpenArea(areas.get(t.dataset.a).layer);
      else map.fitBounds(parcels.get(t.dataset.p).shape.getBounds(), { maxZoom: 19 });
    }
  });

  // ---- clicks on the map while selecting
  for (const l of areaLayers) l.on("click", () => { if (mode === "areas") toggleArea(l); });

  let busy = false;
  map.on("click", async (e) => {
    if (mode !== "parcels" || busy) return;
    if (map.getZoom() < PARCEL_ZOOM) { map.setView(e.latlng, PARCEL_ZOOM); return; }
    const { lat, lng } = e.latlng, d = 0.00002;
    busy = true;
    el.classList.add("busy");
    try {
      const { parcels: found } = await cad.getParcels(lat - d, lng - d, lat + d, lng + d, 20);
      const hit = found.find((r) => cad.inside([lng, lat], { type: "Polygon", coordinates: r.rings }));
      if (hit) toggleParcel(hit);
    } catch (err) {
      render("Katastr teď neodpovídá, zkuste to znovu.");
    } finally {
      busy = false;
      el.classList.remove("busy");
    }
  });
  map.on("zoomend", () => { if (mode === "parcels" && !areas.size && !parcels.size) render(); });
  render();  // the explanation, before anything is picked
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && mode) setMode(null); });
})();
