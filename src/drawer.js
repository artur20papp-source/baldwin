// The filter window (layer switches, price filter, selection) under the button at the left of the top
// bar. The window unfolds out of the button (see the CSS) and the map glides to the right to make room for
// it, back again when it closes. Inlined into map.html by make_map.py after the controls exist; __MAP__ is
// filled in there.
(function () {
  const map = __MAP__;

  const drawer = document.createElement("aside");
  drawer.className = "ds-drawer";
  drawer.innerHTML = `<div class="dt">${t("Filtry", "Filters", "Filtre")}</div>`;
  for (const sel of [".leaflet-control-layers", ".ds-filter", ".ds-select"]) {
    const el = map.getContainer().querySelector(sel);
    if (el) drawer.appendChild(el);
  }
  // the switches in order: the areas first, then transport from metro to rail, parks last
  const ORDER = ["metro", "tram", "bus", "motorway", "rail", "parks"];
  const overlays = drawer.querySelector(".leaflet-control-layers-overlays");
  if (overlays) {
    for (const key of ORDER) {
      const row = [...overlays.children].find((l) => l.querySelector(`[data-k="${key}"]`));
      if (row) overlays.appendChild(row);
    }
  }
  // the data credits the licences (CC BY) ask for, here instead of a line across the bottom of the map
  const credits = document.createElement("div");
  credits.className = "ds-credits";
  credits.textContent = t("Data © IPR Praha · © ČÚZK (katastr, ZABAGED) · zastávky © PID, vše CC BY · Leaflet",
    "Data © IPR Praha · © ČÚZK (cadastre, ZABAGED) · stops © PID, all CC BY · Leaflet",
    "Dáta © IPR Praha · © ČÚZK (kataster, ZABAGED) · zastávky © PID, všetko CC BY · Leaflet");
  drawer.appendChild(credits);
  document.body.appendChild(drawer);
  L.DomEvent.disableClickPropagation(drawer);
  L.DomEvent.disableScrollPropagation(drawer);

  const button = document.createElement("button");
  button.className = "ds-toggle";
  button.title = t("Filtry", "Filters", "Filtre");
  button.innerHTML = '<svg viewBox="0 0 24 24"><path d="M4 7h16M4 17h16"/>'
    + '<circle cx="15" cy="7" r="2.2"/><circle cx="9" cy="17" r="2.2"/></svg>';
  document.querySelector(".ds-bar .ds-left").prepend(button);  // before the search

  // the language switcher at the far right of the bar: its list opens on a click, a choice reloads the page
  const lang = document.querySelector(".ds-lang");
  lang.querySelector(`[data-lang="${window.baldwinLang}"]`).classList.add("on");
  lang.querySelector(".ds-lang-btn").addEventListener("click", (e) => { e.stopPropagation(); lang.classList.toggle("open"); });
  lang.querySelector(".ds-lang-menu").addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (b) window.baldwinSetLang(b.dataset.lang);
    lang.classList.remove("open");
  });
  document.addEventListener("click", (e) => { if (!lang.contains(e.target)) lang.classList.remove("open"); });

  // on a computer the map moves over by half the window's width, so what was in the middle stays in the
  // middle of the free part; on a phone the window comes up from the bottom and the map stays
  const phone = window.matchMedia("(max-width: 700px)");
  let open = false, shifted = 0;
  // stay: close without moving the map back (an area panel is opening and the map flies to it anyway)
  const toggle = (on, stay) => {
    open = on;
    document.body.classList.toggle("drawer-open", on);
    if (on && window.baldwinClosePanel) window.baldwinClosePanel();  // one window at a time on the left
    const want = on && !phone.matches ? Math.round((drawer.offsetWidth + 8) / 2) : 0;
    if (want !== shifted) {
      if (!stay) map.panBy([shifted - want, 0], { duration: 0.55, easeLinearity: 0.2 });
      shifted = want;
    }
  };
  // an area opening closes the window, except while picking areas or parcels for a selection (which lives in it)
  window.baldwinCloseDrawer = () => { if (open && !window.baldwinSelectMode) toggle(false, true); };
  button.addEventListener("click", () => toggle(!open));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && open && !window.baldwinSelectMode) toggle(false);
  });
})();
