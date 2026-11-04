// Search box in the title panel: development areas, localities, parks, metro stations (all local)
// and addresses (ČÚZK RÚIAN, live). Inlined into map.html by make_map.py; __MAP__, __STATIONS__ and
// __PLACES__ (the localities and parks, as names and boxes) are filled in there.
(function () {
  const map = __MAP__;
  const STATIONS = __STATIONS__;
  const PLACES = __PLACES__;  // { k: "L" locality or "P" park, n: name, c: locality code, b: [s, w, n, e] }
  const RUIAN = "https://ags.cuzk.cz/arcgis/rest/services/RUIAN/Vyhledavaci_sluzba_nad_daty_RUIAN/MapServer/exts/GeocodeSOE";
  const MAX = 8;

  // lower-case and without diacritics, so "seberov" finds "Šeberov"
  const norm = (s) => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();

  // ---- local index, built from the layers already on the map
  const index = [];
  for (const key of Object.keys(window)) {
    const geo = window[key];
    if (!key.startsWith("geo_json_") || !geo.eachLayer) continue;
    geo.eachLayer((l) => {
      const p = l.feature && l.feature.properties;
      if (!p) return;
      if (p.area_code) {
        index.push({ type: "Plocha", tag: t("Plocha", "Area", "Plocha"), text: p.area_code,
                     sub: `${p.locality_name} · ${tw(p.stabilita_txt)} ${tw(p.vyuziti_txt)}`,
                     keys: [p.area_code, String(p.id), p.locality_name].map(norm), go: () => window.baldwinOpenArea(l) });
      }
    });
  }
  const box = (b) => L.latLngBounds([b[0], b[1]], [b[2], b[3]]);
  for (const pl of PLACES) {
    if (pl.k === "L") {
      index.push({ type: "Lokalita", tag: t("Lokalita", "Locality", "Lokalita"), text: pl.n,
                   sub: `${t("lokalita", "locality", "lokalita")} ${pl.c}`, keys: [norm(pl.n), pl.c],
                   go: () => map.flyToBounds(box(pl.b), { paddingTopLeft: [40, 140], maxZoom: 16, duration: 0.9 }) });
    } else {
      index.push({ type: "Park", text: pl.n, sub: t("městský park", "city park", "mestský park"), keys: [norm(pl.n)],
                   go: () => map.flyToBounds(box(pl.b), { paddingTopLeft: [40, 140], maxZoom: 17, duration: 0.9 }) });
    }
  }
  for (const s of STATIONS) {
    index.push({ type: "Metro", text: s.name, sub: `${t("linka", "line", "linka")} ${s.lines.join(" · ")}`, keys: [norm(s.name)],
                 go: () => map.flyTo([s.lat, s.lon], 16, { duration: 0.9 }) });
  }

  function localHits(q) {
    const n = norm(q);
    if (!n) return [];
    const scored = [];
    for (const item of index) {
      let best = Infinity;
      for (const k of item.keys) {
        const i = k.indexOf(n);
        if (i >= 0) best = Math.min(best, i === 0 ? (k.length === n.length ? 0 : 1) : 2);
      }
      if (best < Infinity) scored.push([best, item]);
    }
    const order = { Plocha: 0, Metro: 1, Lokalita: 2, Park: 3 };
    scored.sort((a, b) => a[0] - b[0] || order[a[1].type] - order[b[1].type] || a[1].text.localeCompare(b[1].text, "cs"));
    return scored.slice(0, MAX).map((s) => s[1]);
  }

  // ---- addresses from RÚIAN: suggestions while typing, the exact point on select
  let marker = null;
  async function addressHits(q) {
    if (norm(q).length < 3) return [];
    try {
      const url = `${RUIAN}/suggest?text=${encodeURIComponent(q)}&maxSuggestions=5&f=json`;
      const data = await (await fetch(url)).json();
      return (data.suggestions || []).filter((s) => /Praha/.test(s.text)).map((s) => ({
        type: s.type === "Ulice" ? "Ulice" : "Adresa",
        tag: s.type === "Ulice" ? t("Ulice", "Street", "Ulica") : t("Adresa", "Address", "Adresa"), text: s.text.replace(/, \d{3} ?\d{2} Praha.*$/, ""), sub: s.text,
        go: async () => {
          const u = `${RUIAN}/findAddressCandidates?SingleLine=${encodeURIComponent(s.text)}&magicKey=${s.magicKey}&outSR=4326&maxLocations=1&f=json`;
          const c = ((await (await fetch(u)).json()).candidates || [])[0];
          if (!c) return;
          const ll = [c.location.y, c.location.x];
          map.flyTo(ll, s.type === "Ulice" ? 16 : 18, { duration: 0.9 });
          if (marker) map.removeLayer(marker);
          marker = L.circleMarker(ll, { radius: 7, color: "#ffffff", weight: 2, fillColor: "#ffffff", fillOpacity: 0.25 })
            .bindTooltip(s.text).addTo(map);
        },
      }));
    } catch (err) {
      return [];
    }
  }

  // ---- UI
  const input = document.querySelector(".ds-search input");
  input.placeholder = t("Plocha, lokalita, metro, adresa…", "Area, locality, metro, address…", "Plocha, lokalita, metro, adresa…");
  const list = document.querySelector(".ds-results");
  let items = [], active = -1, seq = 0;

  function render() {
    list.innerHTML = items.map((it, i) => `
      <div class="ds-hit${i === active ? " active" : ""}" data-i="${i}">
        <span class="ds-tag">${it.tag || it.type}</span>
        <span class="ds-main">${it.text}</span>
        <span class="ds-sub">${it.sub || ""}</span>
      </div>`).join("");
    list.classList.toggle("open", items.length > 0);
  }

  function choose(i) {
    const it = items[i];
    if (!it) return;
    items = []; active = -1; render();
    input.value = it.text;
    input.blur();
    it.go();
  }

  let timer = null;
  input.addEventListener("input", () => {
    const q = input.value;
    items = localHits(q); active = items.length ? 0 : -1; render();
    clearTimeout(timer);
    const mine = ++seq;
    timer = setTimeout(async () => {
      const extra = await addressHits(q);
      if (mine !== seq) return;  // a newer query is running
      items = localHits(q).concat(extra).slice(0, MAX + 3);
      if (active < 0 && items.length) active = 0;
      render();
    }, 250);
  });
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { active = Math.min(items.length - 1, active + 1); render(); e.preventDefault(); }
    else if (e.key === "ArrowUp") { active = Math.max(0, active - 1); render(); e.preventDefault(); }
    else if (e.key === "Enter") { choose(active); }
    else if (e.key === "Escape") { items = []; render(); input.blur(); }
  });
  list.addEventListener("mousedown", (e) => {
    const hit = e.target.closest(".ds-hit");
    if (hit) { e.preventDefault(); choose(Number(hit.dataset.i)); }
  });
  input.addEventListener("blur", () => setTimeout(() => { items = []; render(); }, 150));
  // "/" anywhere jumps to the search box
  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && document.activeElement !== input) { e.preventDefault(); input.focus(); input.select(); }
  });
  L.DomEvent.disableClickPropagation(document.querySelector(".ds-title"));
  L.DomEvent.disableScrollPropagation(document.querySelector(".ds-title"));
})();
