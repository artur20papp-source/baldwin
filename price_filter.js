// Price filter for the development areas (Kč/m² from the official price map, set by screening.py).
// Inlined into map.html by make_map.py; __MAP__ is filled in there.
(function () {
  const map = __MAP__;
  const STEP = 500;

  // [area layer, its GeoJSON parent], so hidden areas can be taken out of and put back into their layer
  const areas = [];
  for (const key of Object.keys(window)) {
    const geo = window[key];
    if (!key.startsWith("geo_json_") || !geo.eachLayer) continue;
    geo.eachLayer((l) => {
      if (l.feature && l.feature.properties && "price_src" in l.feature.properties) areas.push([l, geo]);
    });
  }
  if (!areas.length) return;

  const prices = areas.map(([l]) => l.feature.properties.price).filter(Boolean);
  const max = Math.ceil(Math.max(...prices) / STEP) * STEP;
  const fmt = (v) => Number(v).toLocaleString("cs-CZ");

  const Filter = L.Control.extend({
    options: { position: "topright" },
    onAdd() {
      const box = L.DomUtil.create("div", "ds-filter");
      box.innerHTML = `
        <div class="ft">Cena pozemku <span class="fv"></span></div>
        <label>Od <input type="range" class="lo" min="0" max="${max}" step="${STEP}" value="0"></label>
        <label>Do <input type="range" class="hi" min="0" max="${max}" step="${STEP}" value="${max}"></label>
        <label class="chk"><input type="checkbox" class="none" checked> i plochy bez ceny</label>
        <div class="fc"></div>
        <div class="fs">Cenová mapa hl. m. Prahy · IPR</div>`;
      L.DomEvent.disableClickPropagation(box);
      L.DomEvent.disableScrollPropagation(box);
      return box;
    },
  });
  const box = new Filter().addTo(map).getContainer();
  const lo = box.querySelector(".lo"), hi = box.querySelector(".hi"), none = box.querySelector(".none");

  function apply() {
    let a = Number(lo.value), b = Number(hi.value);
    if (a > b) [a, b] = [b, a];
    let shown = 0;
    for (const [layer, geo] of areas) {
      const price = layer.feature.properties.price;
      const keep = price ? price >= a && price <= b : none.checked;
      if (keep && !geo.hasLayer(layer)) geo.addLayer(layer);
      if (!keep && geo.hasLayer(layer)) geo.removeLayer(layer);
      if (keep) shown += 1;
    }
    // each slider's track thick and white up to its knob
    for (const el of [lo, hi]) el.style.setProperty("--b", `${el.value / max * 100}%`);
    box.querySelector(".fv").textContent = `${fmt(a)} – ${fmt(b)} Kč/m²`;
    box.querySelector(".fc").textContent = `Zobrazeno ${fmt(shown)} z ${fmt(areas.length)} ploch`;
  }
  for (const el of [lo, hi, none]) el.addEventListener("input", apply);
  apply();
})();
