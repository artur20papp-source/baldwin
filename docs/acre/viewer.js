// Baldwin Acre viewer: the worked example model (Šeberov), shown read-only the way Excel shows it: sheet
// tabs, column letters and row numbers, the file's own widths, heights, fonts, fills, borders, number
// formats and conditional colours, with the values Excel calculated and saved. Clicking a cell shows its
// formula in the bar on top; nothing can be changed. Used by index.html in this folder; MODEL is set there.
(function () {
  const grid = document.getElementById("grid"), tabs = document.getElementById("tabs");
  const barRef = document.getElementById("ref"), barF = document.getElementById("formula");

  // ---- Excel number formats, the ones the model uses (sections pos;neg;zero, quoted text, %, decimals, thousands)
  function sections(fmt) {
    const out = []; let cur = "", q = false;
    for (const ch of fmt) { if (ch === '"') q = !q; if (ch === ";" && !q) { out.push(cur); cur = ""; } else cur += ch; }
    out.push(cur);
    return out;
  }
  const MARK = 0xE000;  // quoted text waits under private-use characters, which no number pattern can match
  function formatNumber(v, fmt) {
    if (!fmt || fmt === "General") {
      return Math.abs(v) >= 1e11 || (v !== 0 && Math.abs(v) < 1e-4) ? v.toExponential(4) : String(Math.round(v * 1e9) / 1e9);
    }
    const sec = sections(fmt);
    let s = sec[0], x = v;
    if (v < 0 && sec[1] !== undefined) { s = sec[1]; x = -v; }
    else if (v === 0 && sec[2] !== undefined) s = sec[2];
    s = s.replace(/\[[^\]]*\]/g, "");  // colours and conditions
    const lits = [];
    s = s.replace(/"([^"]*)"/g, (_, txt) => { lits.push(txt); return String.fromCharCode(MARK + lits.length - 1); });
    if (s.includes("%")) x *= 100;
    const m = s.match(/[#0,]*\.?[#0]+|[#0]+/);
    if (m) {
      const pat = m[0], dec = (pat.split(".")[1] || "").length;
      s = s.replace(pat, x.toLocaleString("en-US", { minimumFractionDigits: dec, maximumFractionDigits: dec,
                                                     useGrouping: pat.includes(",") }));
    }
    let out = "";
    for (const ch of s.replace(/\\(.)/g, "$1").replace(/_./g, " ")) {
      const k = ch.charCodeAt(0) - MARK;
      out += k >= 0 && k < lits.length ? lits[k] : ch;
    }
    return out;
  }
  const valueOf = (cell) => {
    const v = cell.value;
    if (v === null || v === undefined) return null;
    if (typeof v === "object") {
      if ("result" in v) return v.result;
      if (v.richText) return v.richText.map((r) => r.text).join("");
      if (v.error) return v.error;
      if (v.formula || v.sharedFormula) return 0;  // ExcelJS leaves out a saved result of exactly 0
      return null;
    }
    return v;
  };
  const formulaOf = (cell) => {
    const v = cell.value;
    if (v && typeof v === "object" && (v.formula || v.sharedFormula)) return "=" + (cell.formula || v.formula || v.sharedFormula);
    return null;
  };
  const argb = (c) => (c && typeof c.argb === "string" ? "#" + c.argb.slice(-6) : null);
  const BORDER = { thin: "1px solid", hair: "1px solid", dotted: "1px dotted", dashed: "1px dashed", medium: "2px solid",
                   thick: "3px solid", double: "3px double", mediumDashed: "2px dashed" };
  const letters = (n) => { let s = ""; for (n++; n > 0; n = Math.floor((n - 1) / 26)) s = String.fromCharCode(65 + (n - 1) % 26) + s; return s; };
  function decodeRange(ref) {
    const p = (x) => { const m = x.match(/([A-Z]+)(\d+)/); let c = 0; for (const ch of m[1]) c = c * 26 + ch.charCodeAt(0) - 64; return [Number(m[2]), c]; };
    const [a, b = a] = ref.replace(/\$/g, "").split(":"), [r1, c1] = p(a), [r2, c2] = p(b);
    return { r1, c1, r2, c2 };
  }

  // conditional formats: "cell value less than" (the negatives in red) and the colour scales of the sensitivity grids
  function conditional(ws) {
    const fonts = {}, fills = {};
    for (const cf of ws.conditionalFormattings || []) {
      for (const ref of String(cf.ref).split(" ")) {
        const R = decodeRange(ref);
        for (const rule of cf.rules || []) {
          const cells = [];
          for (let r = R.r1; r <= R.r2; r++) for (let c = R.c1; c <= R.c2; c++) {
            const v = valueOf(ws.getCell(r, c)); if (typeof v === "number") cells.push([r, c, v]);
          }
          if (rule.type === "cellIs" && rule.operator === "lessThan") {
            const lim = Number(rule.formulae && rule.formulae[0]);
            const color = argb(rule.style && rule.style.font && rule.style.font.color);
            for (const [r, c, v] of cells) if (v < lim && color) fonts[`${r},${c}`] = color;
          } else if (rule.type === "colorScale" && rule.color && cells.length) {
            const vs = cells.map((x) => x[2]).sort((a, b) => a - b), lo = vs[0], hi = vs[vs.length - 1];
            const mid = vs[Math.floor(vs.length / 2)];
            const rgb = rule.color.map((c) => { const h = (c.argb || "FF000000").slice(-6); return [0, 2, 4].map((i) => parseInt(h.substr(i, 2), 16)); });
            const mix = (a, b, f) => a.map((x, i) => Math.round(x + (b[i] - x) * f));
            for (const [r, c, v] of cells) {
              const col = rgb.length === 3
                ? (v <= mid ? mix(rgb[0], rgb[1], mid === lo ? 1 : (v - lo) / (mid - lo)) : mix(rgb[1], rgb[2], hi === mid ? 1 : (v - mid) / (hi - mid)))
                : mix(rgb[0], rgb[rgb.length - 1], hi === lo ? 1 : (v - lo) / (hi - lo));
              fills[`${r},${c}`] = `rgb(${col.join(",")})`;
            }
          }
        }
      }
    }
    return { fonts, fills };
  }

  function render(ws) {
    const rows = Math.max(ws.rowCount, 1) + 3, cols = Math.max(ws.columnCount, 1) + 2;
    const merged = {}, hidden = new Set();
    for (const ref of (ws.model && ws.model.merges) || []) {
      const R = decodeRange(ref);
      merged[`${R.r1},${R.c1}`] = [R.r2 - R.r1 + 1, R.c2 - R.c1 + 1];
      for (let r = R.r1; r <= R.r2; r++) for (let c = R.c1; c <= R.c2; c++) if (r !== R.r1 || c !== R.c1) hidden.add(`${r},${c}`);
    }
    const cond = conditional(ws);
    const width = (c) => Math.round((ws.getColumn(c).width || 8.43) * 7 + 5);
    let h = '<table><colgroup><col style="width:34px">';
    for (let c = 1; c <= cols; c++) h += `<col style="width:${width(c)}px">`;
    h += '</colgroup><tr><td class="hc hr corner"></td>';
    for (let c = 1; c <= cols; c++) h += `<td class="hc">${letters(c - 1)}</td>`;
    h += "</tr>";
    for (let r = 1; r <= rows; r++) {
      h += `<tr style="height:${Math.round((ws.getRow(r).height || 15) * 96 / 72)}px"><td class="hr">${r}</td>`;
      for (let c = 1; c <= cols; c++) {
        const key = `${r},${c}`;
        if (hidden.has(key)) continue;
        const cell = ws.getCell(r, c), v = valueOf(cell), st = [];
        const f = cell.font || {}, fill = cell.fill, b = cell.border || {}, al = cell.alignment || {};
        const bg = cond.fills[key] || (fill && fill.type === "pattern" && fill.pattern === "solid" && argb(fill.fgColor));
        if (bg) st.push(`background:${bg}`);
        st.push(`color:${cond.fonts[key] || argb(f.color) || "#ececec"}`);
        // single quotes around the font: this ends up inside style="…"
        st.push(`font:${f.italic ? "italic " : ""}${f.bold ? 600 : 400} ${Math.round((f.size || 10) * 96 / 72)}px ${f.name ? `'${f.name}',` : ""}Arial,sans-serif`);
        for (const side of ["top", "bottom", "left", "right"]) {
          const e = b[side]; if (e && e.style) st.push(`border-${side}:${BORDER[e.style] || "1px solid"} ${argb(e.color) || "#3a3a3a"}`);
        }
        const isNum = typeof v === "number";
        st.push(`text-align:${al.horizontal && al.horizontal !== "general" ? al.horizontal : isNum ? "right" : "left"}`);
        if (al.indent) st.push(`padding-left:${4 + al.indent * 9}px`);
        const text = v === null ? "" : isNum ? formatNumber(v, cell.numFmt) : String(v);
        const span = merged[key] ? ` rowspan="${merged[key][0]}" colspan="${merged[key][1]}"` : "";
        h += `<td data-a="${letters(c - 1)}${r}"${span} style="${st.join(";")}">${text.replace(/&/g, "&amp;").replace(/</g, "&lt;")}</td>`;
      }
      h += "</tr>";
    }
    grid.innerHTML = h + "</table>";
    grid.scrollTo(0, 0);
    barRef.textContent = ""; barF.textContent = "";
    grid.onclick = (e) => {
      const td = e.target.closest("td[data-a]");
      if (!td) return;
      grid.querySelectorAll("td.sel").forEach((x) => x.classList.remove("sel"));
      td.classList.add("sel");
      const cell = ws.getCell(td.dataset.a), v = valueOf(cell);
      barRef.textContent = td.dataset.a;
      barF.textContent = formulaOf(cell) || (v === null ? "" : String(v));
    };
  }

  (async () => {
    try {
      const res = await fetch(window.MODEL);
      if (!res.ok) throw new Error(res.status);
      const book = new ExcelJS.Workbook();
      await book.xlsx.load(await res.arrayBuffer());
      tabs.innerHTML = book.worksheets.map((ws, i) => `<button data-i="${i}">${ws.name}</button>`).join("");
      const show = (i) => {
        tabs.querySelectorAll("button").forEach((b) => b.classList.toggle("on", Number(b.dataset.i) === i));
        render(book.worksheets[i]);
      };
      tabs.onclick = (e) => { const b = e.target.closest("button"); if (b) show(Number(b.dataset.i)); };
      show(0);
    } catch (err) {
      grid.innerHTML = `<div class="msg">${t("Model se nepodařilo načíst.", "The model could not be loaded.", "Model sa nepodarilo načítať.")}</div>`;
    }
  })();
})();
