// Motorways and railways in Prague (ČÚZK ZABAGED) as two switches in the layer list. Their lines sit
// in their own files next to the page (motorways.geojson, rail.geojson), fetched once the map is up, so
// they don't weigh on the page. Drawn just above the city's fill, under everything else. Inlined into
// map.html by make_map.py before the filter window is built; the tokens are filled in there.
(function () {
  const map = __MAP__;
  const control = __CONTROL__;
  const LAYERS = __LAYERS__;  // [{ file, label, style }]

  window.baldwinLines = [];
  for (const def of LAYERS) {
    const group = L.featureGroup();
    window.baldwinLines.push(group);
    control.addOverlay(group, def.label);
    group.addTo(map);
    fetch(def.file).then((r) => r.json()).then((geo) => {
      L.geoJSON(geo, { interactive: false, style: def.style, smoothFactor: 1.5 }).addTo(group);
      window.baldwinLinesBack();
      window.baldwinCityBack();
    }).catch(() => {});
  }
  // keep them under the areas and transport, just above the city (called again whenever a layer is switched on)
  window.baldwinLinesBack = () => { for (const g of window.baldwinLines) if (map.hasLayer(g)) g.bringToBack(); };
})();
