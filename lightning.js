// Lightning on the start screen: while the orb is hovered and its flare spreads, bolts crack out from
// behind the ball towards the viewer. Each bolt is a fresh jagged path (midpoint displacement) with a
// few thin branches; it starts thin at the orb and widens as it travels out (coming at the camera),
// glows softly, flickers and fades. Half-transparent yellow, orange, red and purple. Inlined into
// map.html by make_map.py.
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
  function resize() {
    const dpr = window.devicePixelRatio || 1;
    w = canvas.width = Math.round(innerWidth * dpr);
    h = canvas.height = Math.round(innerHeight * dpr);
  }
  resize();
  addEventListener("resize", resize);

  // a jagged path from a to b: split each segment at its middle and push the middle sideways
  function jagged(a, b, rough) {
    let pts = [a, b];
    for (let level = 0; level < 7; level++) {
      const next = [pts[0]];
      for (let i = 1; i < pts.length; i++) {
        const [x1, y1] = pts[i - 1], [x2, y2] = pts[i];
        const len = Math.hypot(x2 - x1, y2 - y1), off = (Math.random() - 0.5) * len * rough;
        next.push([(x1 + x2) / 2 + (-(y2 - y1) / len) * off, (y1 + y2) / 2 + ((x2 - x1) / len) * off], pts[i]);
      }
      pts = next;
    }
    return pts;
  }

  function bolt() {
    const r = orb.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
    const cx = (r.left + r.width / 2) * dpr, cy = (r.top + r.height / 2) * dpr;
    const angle = Math.random() * Math.PI * 2, reach = Math.hypot(w, h) * (0.45 + Math.random() * 0.25);
    const start = [cx + Math.cos(angle) * r.width * 0.3 * dpr, cy + Math.sin(angle) * r.width * 0.3 * dpr];
    const end = [cx + Math.cos(angle) * reach, cy + Math.sin(angle) * reach];
    const main = jagged(start, end, 0.32);
    const paths = [{ pts: main, from: 0, width: 1 }];
    for (let k = 0; k < 2 + Math.floor(Math.random() * 3); k++) {  // a few branches off the main bolt
      const i = Math.floor(main.length * (0.2 + Math.random() * 0.5));
      const [bx, by] = main[i], a = angle + (Math.random() - 0.5) * 1.1, l = reach * (0.12 + Math.random() * 0.2);
      paths.push({ pts: jagged([bx, by], [bx + Math.cos(a) * l, by + Math.sin(a) * l], 0.35), from: i / main.length, width: 0.45 });
    }
    return { paths, color: COLORS[Math.floor(Math.random() * COLORS.length)], born: performance.now(),
             life: 650 + Math.random() * 450, alpha: 0.32 + Math.random() * 0.22, dpr };
  }

  // draw a path tapering from thin (at the orb, far away) to wide (near the viewer)
  function stroke(p, upTo, base, color, alpha, blur) {
    const n = Math.max(2, Math.floor(p.pts.length * upTo));
    ctx.strokeStyle = `rgba(${color},${alpha})`;
    ctx.shadowColor = `rgba(${color},${alpha})`;
    ctx.shadowBlur = blur;
    for (let i = 1; i < n; i++) {
      const t = p.from + (i / p.pts.length) * (1 - p.from);
      ctx.lineWidth = base * p.width * (0.35 + t * 2.4);
      ctx.beginPath();
      ctx.moveTo(p.pts[i - 1][0], p.pts[i - 1][1]);
      ctx.lineTo(p.pts[i][0], p.pts[i][1]);
      ctx.stroke();
    }
  }

  let bolts = [], hoverStart = 0, last = 0, running = false;
  function frame(now) {
    ctx.clearRect(0, 0, w, h);
    const hovering = orb.matches(":hover") && !menu.classList.contains("gone");
    if (hovering) {
      if (!hoverStart) hoverStart = now;
      const grow = Math.min(1, (now - hoverStart) / GROW);
      // from a bolt every few seconds at first to about two a second once the flare fills the room
      if (grow > 0.12 && Math.random() < (now - last) / 1000 * (0.25 + grow * 1.8)) bolts.push(bolt());
    } else hoverStart = 0;
    last = now;
    ctx.lineCap = "round";
    ctx.globalCompositeOperation = "lighter";
    bolts = bolts.filter((b) => now - b.born < b.life);
    for (const b of bolts) {
      const age = (now - b.born) / b.life;
      const reveal = Math.min(1, age / 0.18);                       // shoots out fast...
      const fade = age < 0.18 ? 1 : Math.pow(1 - (age - 0.18) / 0.82, 1.6);  // ...then dies away
      const flicker = 0.75 + Math.random() * 0.25;
      const a = b.alpha * fade * flicker;
      for (const p of b.paths) {
        const upTo = Math.max(0, (reveal - p.from) / (1 - p.from));
        if (upTo <= 0) continue;
        stroke(p, upTo, 3.2 * b.dpr, b.color, a * 0.35, 18 * b.dpr);  // soft glow around it
        stroke(p, upTo, 1.1 * b.dpr, "255,240,225", a * 0.55, 4 * b.dpr);  // thin hot core
      }
    }
    ctx.globalCompositeOperation = "source-over";
    if (menu.classList.contains("gone") && !bolts.length) { running = false; return; }
    requestAnimationFrame(frame);
  }
  running = true;
  requestAnimationFrame(frame);
})();
