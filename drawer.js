// The filter window (layer switches, price filter, selection) under the button at the left of the top
// bar. The window unfolds out of the button (see the CSS)
// and floats over the map, so the map itself stays still. Inlined into map.html by make_map.py after the
// controls exist; __MAP__ is filled in there.
(function () {
  const map = __MAP__;

  const drawer = document.createElement("aside");
  drawer.className = "ds-drawer";
  drawer.innerHTML = '<div class="dt">Filtry</div>';
  for (const sel of [".leaflet-control-layers", ".ds-filter", ".ds-select"]) {
    const el = map.getContainer().querySelector(sel);
    if (el) drawer.appendChild(el);
  }
  document.body.appendChild(drawer);
  L.DomEvent.disableClickPropagation(drawer);
  L.DomEvent.disableScrollPropagation(drawer);

  const button = document.createElement("button");
  button.className = "ds-toggle";
  button.title = "Filtry";
  button.innerHTML = '<svg viewBox="0 0 24 24"><path d="M4 7h16M4 17h16"/>'
    + '<circle cx="15" cy="7" r="2.2"/><circle cx="9" cy="17" r="2.2"/></svg>';
  document.querySelector(".ds-bar .ds-left").appendChild(button);

  let open = false;
  const toggle = (on) => { open = on; document.body.classList.toggle("drawer-open", on); };
  button.addEventListener("click", () => toggle(!open));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && open && !window.baldwinSelectMode) toggle(false);
  });
})();
