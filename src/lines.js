// Motorways and railways in Prague (ČÚZK ZABAGED, with PID's train stations) as two switches in the layer list. Their lines sit
// in their own files in data/ (motorways.geojson, rail.geojson), fetched once the map is up, so
// they don't weigh on the page. Drawn just above the city's fill, under everything else. Inlined into
// map.html by make_map.py before the filter window is built; the tokens are filled in there.
(function () {
  const map = __MAP__;
  const control = __CONTROL__;
  const LAYERS = __LAYERS__;  // [{ file, label, style }]

  window.baldwinLines = [];
  map.createPane("line-stops").style.zIndex = 455;  // stations above the areas, so their names show on hover
  for (const def of LAYERS) {
    const group = L.featureGroup();
    window.baldwinLines.push(group);
    control.addOverlay(group, def.label);
    group.addTo(map);
    fetch(def.file).then((r) => r.json()).then((geo) => {
      // lines under the map's clicks; stations (points) as small dots like the tram and bus stops, named on hover
      L.geoJSON(geo, { filter: (f) => f.geometry.type !== "Point", interactive: false, style: def.style,
                       smoothFactor: 1.5 }).addTo(group);
      const stops = L.geoJSON(geo, {
        filter: (f) => f.geometry.type === "Point",
        pointToLayer: (f, ll) => L.circleMarker(ll, { pane: "line-stops", radius: 2.5, weight: 1.5, color: def.style.color,
                                                      fillColor: def.style.stop, fillOpacity: 1 }).bindTooltip(f.properties.n),
      });
      // the stations only zoomed in, like the metro's
      const byZoom = () => { if (map.getZoom() >= (def.style.stopsFrom || 0)) group.addLayer(stops); else group.removeLayer(stops); };
      map.on("zoomend", byZoom);
      byZoom();
      window.baldwinLinesBack();
      window.baldwinCityBack();
    }).catch(() => {});
  }
  // keep them under the areas and transport, just above the city (called again whenever a layer is switched on)
  window.baldwinLinesBack = () => { for (const g of window.baldwinLines) if (map.hasLayer(g)) g.bringToBack(); };
})();
