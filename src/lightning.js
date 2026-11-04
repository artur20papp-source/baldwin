// Lightning on the start screen: while the orb is hovered and its flare spreads, bolts crack out all
// around the ball. Each one starts on the orb's edge, curls partly around it and snakes outwards,
// turning at every step, with a fine jagged edge and a few branches; short ones crawl around the rim.
// It widens as it travels out (coming at the camera), glows softly and fades. Half-transparent yellow,
// orange, red and purple. Inlined into map.html by make_map.py.
//
// Speed: no canvas shadow blur (that is what made it lag); the glow is the same path stroked wide and
// faint, then thin and bright, at normal (not retina) resolution.
(function () {
  const menu = document.querySelector(".ds-menu");
  const orb = menu.querySelector(".orb");
  const COLORS = ["255,214,110", "255,146,64", "236,72,46", "168,110,255"];  // yellow, orange, red, purple
  const GROW = 7000;  // ms until bolts come at full rate, the same time the flare takes to fill the room

  const canvas = document.createElement("canvas");
  canvas.className = "orb-lightning";
  menu.insertBefore(canvas, menu.firstChild);  // behind the orb
  const ctx = canvas.getContext("2d");
  let w = 0, h = 0;
  const resize = () => { w = canvas.width = innerWidth; h = canvas.height = innerHeight; };
  resize();
  addEventListener("resize", resize);

  const rnd = (a, b) => a + Math.random() * (b - a);

  // a wandering path: small steps whose heading drifts, curls and jerks, roughened with midpoint noise
  function wander(x, y, heading, steps, step, curl, pull = null) {  // pull: direction it is drawn towards
    const pts = [[x, y]];
    for (let i = 0; i < steps; i++) {
      heading += curl + rnd(-0.42, 0.42);
      if (pull !== null) heading += Math.atan2(Math.sin(pull - heading), Math.cos(pull - heading)) * 0.07;
      x += Math.cos(heading) * step * rnd(0.6, 1.4);
      y += Math.sin(heading) * step * rnd(0.6, 1.4);
      pts.push([x, y]);
    }
    const out = [pts[0]];  // one level of midpoint jitter for the fine crackle
    for (let i = 1; i < pts.length; i++) {
      const [x1, y1] = pts[i - 1], [x2, y2] = pts[i], j = step * 0.35;
      out.push([(x1 + x2) / 2 + rnd(-j, j), (y1 + y2) / 2 + rnd(-j, j)], pts[i]);
    }
    return out;
  }

  function bolt() {
    const r = orb.getBoundingClientRect();
    const cx = r.left + r.width / 2, cy = r.top + r.height / 2, R = r.width / 2;
    const at = Math.random() * Math.PI * 2;               // where on the orb's edge it starts
    const x = cx + Math.cos(at) * R * 0.92, y = cy + Math.sin(at) * R * 0.92;
    const crawl = Math.random() < 0.35;                   // a short one creeping round the rim
    const side = Math.random() < 0.5 ? 1 : -1;
    // start partly along the rim (tangent), then bend outwards; crawlers keep curling round the ball
    const heading = at + side * (crawl ? Math.PI / 2 : rnd(0.5, 1.2));
    const curl = crawl ? side * (rnd(10, 16) / R) : -side * rnd(0.02, 0.06);
    const steps = crawl ? Math.round(rnd(10, 18)) : Math.round(rnd(22, 40));
    const step = crawl ? R * 0.11 : Math.hypot(w, h) * rnd(0.014, 0.022);
    const main = wander(x, y, heading, steps, step, curl, crawl ? null : at);
    const paths = [{ pts: main, from: 0, width: crawl ? 0.6 : 1 }];
    for (let k = 0; k < (crawl ? 1 : 2 + Math.floor(Math.random() * 3)); k++) {
      const i = Math.floor(main.length * rnd(0.15, 0.7));
      const [bx, by] = main[i], [px, py] = main[Math.max(0, i - 1)];
      const dir = Math.atan2(by - py, bx - px) + rnd(-1, 1);
      paths.push({ pts: wander(bx, by, dir, Math.round(steps * rnd(0.2, 0.4)), step * 0.8, rnd(-0.05, 0.05)),
                   from: i / main.length, width: 0.45 });
    }
    return { paths, color: COLORS[Math.floor(Math.random() * COLORS.length)], born: performance.now(),
             life: rnd(650, 1050), alpha: rnd(0.45, 0.65) };
  }

  // a tapered path (thin at the orb, wider towards the viewer), stroked in a few chunks of rising width
  function stroke(p, upTo, base) {
    const n = Math.max(2, Math.floor(p.pts.length * upTo)), chunks = 4, per = Math.ceil(n / chunks);
    for (let c = 0; c < chunks; c++) {
      const a = c * per, b = Math.min(n - 1, a + per);
      if (b <= a) break;
      const t = p.from + ((a + b) / 2 / p.pts.length) * (1 - p.from);
      ctx.lineWidth = base * p.width * (0.4 + t * 2.2);
      ctx.beginPath();
      ctx.moveTo(p.pts[a][0], p.pts[a][1]);
      for (let i = a + 1; i <= b; i++) ctx.lineTo(p.pts[i][0], p.pts[i][1]);
      ctx.stroke();
    }
  }

  let bolts = [], hoverStart = 0, last = 0, dirty = false;
  function frame(now) {
    const hovering = orb.matches(":hover") && !menu.classList.contains("gone");
    if (hovering) {
      if (!hoverStart) hoverStart = now;
      const grow = Math.min(1, (now - hoverStart) / GROW);
      // from a bolt every couple of seconds at first to about three a second once the flare fills the room
      if (grow > 0.1 && Math.random() < (now - last) / 1000 * (0.4 + grow * 2.6)) bolts.push(bolt());
    } else hoverStart = 0;
    last = now;
    bolts = bolts.filter((b) => now - b.born < b.life);
    if (bolts.length || dirty) {  // nothing to draw: leave the canvas alone
      ctx.clearRect(0, 0, w, h);
      ctx.lineCap = ctx.lineJoin = "round";
      ctx.globalCompositeOperation = "lighter";
      for (const b of bolts) {
        const age = (now - b.born) / b.life;
        const reveal = Math.min(1, age / 0.16);                                   // shoots out fast...
        const fade = age < 0.16 ? 1 : Math.pow(1 - (age - 0.16) / 0.84, 1.6);    // ...then dies away
        const a = b.alpha * fade * rnd(0.75, 1);                                  // flicker
        for (const p of b.paths) {
          const upTo = Math.max(0, (reveal - p.from) / (1 - p.from));
          if (upTo <= 0) continue;
          ctx.strokeStyle = `rgba(${b.color},${a * 0.12})`; stroke(p, upTo, 9);   // wide faint glow
          ctx.strokeStyle = `rgba(${b.color},${a * 0.35})`; stroke(p, upTo, 3.2); // inner glow
          ctx.strokeStyle = `rgba(255,240,225,${a * 0.6})`; stroke(p, upTo, 1);   // thin hot core
        }
      }
      ctx.globalCompositeOperation = "source-over";
      dirty = bolts.length > 0;
    }
    if (menu.classList.contains("gone") && !bolts.length) return;  // on the map: stop for good
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
})();
