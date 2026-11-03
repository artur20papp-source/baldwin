// Easter egg: zoom out to __SKY_ZOOM__ and the map disappears under drifting clouds, with the airport (PRG)
// glowing above them and planes taking off. Inlined into map.html by make_map.py; the tokens are
// filled in there.
(function () {
  const map = __MAP__;
  const AIRPORT = __AIRPORT__;
  const PLANE = __PLANE__;
  const FLIGHTS = __FLIGHTS__;
  const SKY_ZOOM = __SKY_ZOOM__;

  // Procedural cumulus: fractal noise turned into cloud alpha, lit from the upper left so the tops are
  // white and the undersides blue-grey. stitchTiles makes each tile seamless, so two side by side can
  // drift forever without a visible join.
  function cloudLayer(id, freq, seed, cover) {
    const tile = `<svg preserveAspectRatio="none" viewBox="0 0 1600 900"><defs>
      <filter id="${id}" x="0" y="0" width="100%" height="100%" color-interpolation-filters="sRGB">
        <feTurbulence type="fractalNoise" baseFrequency="${freq}" numOctaves="5" seed="${seed}" stitchTiles="stitch" result="noise"/>
        <feColorMatrix in="noise" type="matrix" result="shape"
          values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  ${cover} 0 0 0 ${-cover * 0.47}"/>
        <feDiffuseLighting in="noise" surfaceScale="6" lighting-color="#ffffff" result="light">
          <feDistantLight azimuth="235" elevation="38"/>
        </feDiffuseLighting>
        <feColorMatrix in="light" type="matrix" result="tinted"
          values="0.3 0 0 0 0.72  0.27 0 0 0 0.76  0.2 0 0 0 0.84  0 0 0 0 1"/>
        <feComposite in="tinted" in2="shape" operator="in"/>
      </filter></defs><rect width="1600" height="900" filter="url(#${id})"/></svg>`;
    return tile + tile;
  }

  const sky = document.createElement("div");
  sky.className = "ds-sky";
  const planes = FLIGHTS.map((p, i) =>
    `<div class="plane" style="offset-path: path('${p}'); animation-delay:${i * 1.75}s">${PLANE}</div>`).join("");
  sky.innerHTML = `<div class="ds-tint"></div>
    <div class="ds-layer back">${cloudLayer("ds-cloud-back", "0.0018 0.003", 7, 3.8)}</div>
    <div class="ds-layer front">${cloudLayer("ds-cloud-front", "0.0026 0.0042", 19, 4.2)}</div>
    <div class="ds-airport"><div class="ap-glow"></div><div class="ap-badge">PRG</div>${planes}
      <div class="ap-name">Letiště Václava Havla</div></div>`;
  map.getContainer().appendChild(sky);

  // keep the airport pinned to its spot on the map while the map moves under the clouds
  const airport = sky.querySelector(".ds-airport");
  const place = () => {
    const p = map.latLngToContainerPoint(AIRPORT);
    airport.style.transform = `translate(${p.x}px, ${p.y}px)`;
  };
  const toggle = () => {
    map.getContainer().classList.toggle("sky", map.getZoom() <= SKY_ZOOM);
    place();
  };
  map.on("move zoom zoomend", place);
  map.on("zoomend", toggle);
  toggle();
})();
