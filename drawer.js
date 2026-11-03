// Drawer on the right with the layer switches, the price filter and the selection. The icon at the top
// right opens it: the drawer slides in while the map glides left, so what was in the middle stays in
// view. Inlined into map.html by make_map.py after the controls exist; __MAP__ is filled in there.
(function () {
  const map = __MAP__;
  const W = 360;  // drawer width, px (same as .ds-drawer in the CSS)
  const GLIDE = { duration: 0.6, easeLinearity: 0.2 };  // a soft ease-out, like the drawer's CSS curve

  const drawer = document.createElement("aside");
  drawer.className = "ds-drawer";
  drawer.innerHTML = '<div class="dt">Filtry a výběr</div>';
  for (const sel of [".leaflet-control-layers", ".ds-filter", ".ds-select"]) {
    const el = map.getContainer().querySelector(sel);
    if (el) drawer.appendChild(el);
  }
  document.body.appendChild(drawer);
  L.DomEvent.disableClickPropagation(drawer);
  L.DomEvent.disableScrollPropagation(drawer);

  const button = document.createElement("button");
  button.className = "ds-toggle";
  button.title = "Filtry a výběr";
  button.innerHTML = '<svg viewBox="0 0 24 24"><path d="M4 7h9M17 7h3M4 17h3M11 17h9"/>'
    + '<circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/></svg>';
  document.body.appendChild(button);

  // Opening: glide the map left by half the drawer while it slides over the right edge, then narrow the
  // map to the free space (left-anchored, so nothing jumps). Closing does the same in reverse.
  // On phones the drawer is a bottom sheet (see the CSS), so the map stays as it is.
  const phone = () => window.matchMedia("(max-width: 700px)").matches;
  const box = map.getContainer();
  let open = false;
  function toggle(on) {
    if (on === open) return;
    open = on;
    document.body.classList.toggle("drawer-open", on);
    if (phone() && box.style.width !== `calc(100% - ${W}px)`) return;
    if (on) {
      map.panBy([W / 2, 0], GLIDE);
      map.once("moveend", () => {
        if (!open) return;
        box.style.width = `calc(100% - ${W}px)`;
        map.invalidateSize({ pan: false });
      });
    } else {
      box.style.width = "100%";
      map.invalidateSize({ pan: false });
      map.panBy([-W / 2, 0], GLIDE);
    }
  }
  button.addEventListener("click", () => toggle(!open));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && open && !window.baldwinSelectMode) toggle(false);
  });
})();
