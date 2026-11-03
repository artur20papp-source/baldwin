// "Export to Baldwin Acre": downloads the Baldwin Acre appraisal model as an empty template (every sheet,
// with the same cells, labels, formulas, fonts, fills, borders and number formats, read from the model
// when the map is built, but none of its numbers), with only what the map knows about the place filled
// into Inputs: the site area (with its farmland share as a note), the max building footprint
// (Metropolitní plán Zz) and the sell price (the city's price map), each with its source beside it.
// Every other input is an assumption about the project and stays empty for the analyst. Inlined into
// map.html by make_map.py; __ACRE__ is filled in there. ExcelJS loads on first use.
(function () {
  const T = __ACRE__;
  const EXAMPLE = __EXAMPLE__;  // the area the model is built on: there the filled model itself is handed out
  const EXCELJS = "https://cdn.jsdelivr.net/npm/exceljs@4.4.0/dist/exceljs.min.js";
  const num = (v) => Math.round(v).toLocaleString("cs-CZ");
  const INPUTS = T.sheets.find((s) => s.name === "Inputs");

  let loading = null;
  const load = () => loading || (loading = new Promise((ok, fail) => {
    const s = document.createElement("script");
    s.src = EXCELJS; s.onload = ok; s.onerror = () => { loading = null; fail(new Error("ExcelJS did not load")); };
    document.head.appendChild(s);
  }));

  // the row of a label in column B of Inputs (by label, so the export follows the model if rows move)
  const rowOf = (label) => { const c = INPUTS.cells.find((x) => x.a[0] === "B" && x.v === label); return c ? c.a.slice(1) : null; };

  function sheet(wb, s) {
    const ws = wb.addWorksheet(s.name, { views: [{ showGridLines: false }] });
    for (const [col, w] of Object.entries(s.widths)) ws.getColumn(col).width = w;
    for (const c of s.cells) {
      const cell = ws.getCell(c.a);
      if (c.f) cell.value = { formula: c.f };
      else if (c.v !== undefined) cell.value = c.v;
      cell.font = { name: c.n, size: c.sz, bold: c.b, italic: c.i, color: c.c ? { argb: c.c } : undefined };
      if (c.fmt) cell.numFmt = c.fmt;
      if (c.bg) cell.fill = { type: "pattern", pattern: "solid", fgColor: { argb: c.bg } };
      if (c.bd) cell.border = Object.fromEntries(Object.entries(c.bd).map(([side, [style, color]]) =>
        [side, { style, color: color ? { argb: color } : undefined }]));
      if (c.al) cell.alignment = { horizontal: c.al[0] || undefined, indent: c.al[1] || undefined };
    }
    for (const range of s.merged) ws.mergeCells(range);
    return ws;
  }

  function download(blob, name) {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  }

  // d: { siteArea, label, file, date, codes (the picked areas, if areas), price (Kč/m²) and zz (%) or null,
  //      each area-weighted when several areas are picked (priceMixed / zzMixed say so), zpfM2 or null }
  window.baldwinExportAcre = async (d) => {
    if (d.codes && d.codes.length === 1 && d.codes[0] === EXAMPLE.area) {  // the worked example
      const res = await fetch(EXAMPLE.file);
      if (!res.ok) throw new Error("the example model is missing");
      return download(await res.blob(), `Baldwin Acre - ${d.file} (example).xlsx`);
    }
    await load();
    const wb = new ExcelJS.Workbook();
    wb.calcProperties.fullCalcOnLoad = true;  // the formulas compute when Excel opens it
    const sheets = Object.fromEntries(T.sheets.map((s) => [s.name, sheet(wb, s)]));
    const ws = sheets.Inputs;

    const note = (addr, text) => {
      const cell = ws.getCell(addr);
      cell.value = text;
      cell.font = { name: "Arial", size: 9, italic: true, color: { argb: "FF7F7F7F" } };
    };
    // what the map knows about the place; everything else in the model is the analyst's assumption
    const fill = (label, value, source) => {
      const r = rowOf(label);
      if (!r || value === null || value === undefined) return;
      ws.getCell("C" + r).value = value;
      note("E" + r, source);
    };
    fill("Site area", Math.round(d.siteArea),
         `Baldwin Palantir: ${d.label}` + (d.zpfM2 ? ` · z toho ZPF ~${num(d.zpfM2)} m² (${Math.round(d.zpfM2 / d.siteArea * 100)} %)` : ""));
    fill("Max house footprint", d.zz === null ? null : d.zz / 100,
         "Metropolitní plán: Zz, základní zastavěnost (čl. 95)" + (d.zzMixed ? ", průměr vážený výměrou" : ""));
    fill("Sell price (incl. VAT)", d.price ? Math.round(d.price) : null,
         "cenová mapa stavebních pozemků hl. m. Prahy" + (d.priceMixed ? ", průměr vážený výměrou" : ""));
    const sub = INPUTS.cells.find((x) => x.a === "B3");
    if (sub) ws.getCell("B3").value = `${sub.v}  ·  site from Baldwin Palantir, ${d.date}`;

    download(new Blob([await wb.xlsx.writeBuffer()], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }),
             `Baldwin Acre - ${d.file}.xlsx`);
  };
})();
