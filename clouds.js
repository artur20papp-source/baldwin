// Dark clouds on the start screen: while the orb is hovered they billow out from behind the ball,
// slowly growing, turning and drifting away, their undersides faintly lit by the fire; the longer you
// hover, the more of them and the darker. They sit under the lightning. Inlined into map.html by
// make_map.py.
//
// Speed: a few cloud shapes are painted once into small offscreen canvases; each frame only draws
// moved, scaled and faded copies of them, at most 22, on a half-resolution canvas (clouds are soft).
(function () {
  const menu = document.querySelector(".ds-menu");
  const orb = menu.querySelector(".orb");
  const GROW = 9000;  // ms of hovering until the clouds are at their thickest
  const rnd = (a, b) => a + Math.random() * (b - a);

  // ---- cloud shapes: many overlapping soft dark puffs, warmer and lighter on the underside
  const S = 256;
  function shape() {
    const c = document.createElement("canvas");
    c.width = c.height = S;
    const g = c.getContext("2d");
    for (let i = 0; i < 46; i++) {
      const a = Math.random() * Math.PI * 2, d = Math.pow(Math.random(), 0.7) * S * 0.28;
      const x = S / 2 + Math.cos(a) * d, y = S / 2 + Math.sin(a) * d * 0.75, r = rnd(S * 0.1, S * 0.22);
      const under = y > S / 2 + S * 0.06;  // lower puffs catch the firelight from below
      const grad = g.createRadialGradient(x, y, 0, x, y, r);
      grad.addColorStop(0, under ? "rgba(62,24,14,.34)" : "rgba(12,9,9,.5)");
      grad.addColorStop(0.6, under ? "rgba(40,16,10,.16)" : "rgba(9,7,7,.24)");
      grad.addColorStop(1, "rgba(0,0,0,0)");
      g.fillStyle = grad;
      g.beginPath();
      g.arc(x, y, r, 0, Math.PI * 2);
      g.fill();
    }
    return c;
  }
  const SHAPES = [shape(), shape(), shape(), shape(), shape()];

  const canvas = document.createElement("canvas");
  canvas.className = "orb-clouds";
  menu.insertBefore(canvas, menu.querySelector(".orb-lightning") || menu.firstChild);  // under the lightning
  const ctx = canvas.getContext("2d");
  let w = 0, h = 0;
  const Q = 0.5;  // canvas resolution: half, stretched to the screen by CSS
  const resize = () => { w = canvas.width = Math.round(innerWidth * Q); h = canvas.height = Math.round(innerHeight * Q); };
  resize();
  addEventListener("resize", resize);

  function cloud(intensity) {
    const r = orb.getBoundingClientRect();
    const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    const a = Math.random() * Math.PI * 2, speed = rnd(14, 38);
    return { x: cx + Math.cos(a) * r.width * 0.2, y: cy + Math.sin(a) * r.width * 0.2,
             vx: Math.cos(a) * speed, vy: Math.sin(a) * speed * 0.8 - rnd(0, 6),  // a little rise
             size0: r.width * rnd(0.8, 1.2), size1: r.width * rnd(2.2, 3.2), spin: rnd(-0.08, 0.08), rot: rnd(0, 6.28),
             img: SHAPES[Math.floor(Math.random() * SHAPES.length)], born: performance.now(), life: rnd(7000, 11000),
             alpha: rnd(0.55, 0.9) * (0.5 + intensity * 0.5) };
  }

  let clouds = [], hoverStart = 0, last = performance.now(), fadeOut = 1, drawn = false;
  function frame(now) {
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;
    const hovering = orb.matches(":hover") && !menu.classList.contains("gone");
    if (hovering) {
      if (!hoverStart) hoverStart = now;
      fadeOut = Math.min(1, fadeOut + dt * 0.8);
      const grow = Math.min(1, (now - hoverStart) / GROW);
      // a puff now and then at first, a steady billowing (about two a second) once fully grown
      if (grow > 0.05 && clouds.length < 22 && Math.random() < dt * (0.4 + grow * 1.8)) clouds.push(cloud(grow));
    } else {
      hoverStart = 0;
      fadeOut = Math.max(0, fadeOut - dt * 0.6);  // let go: the clouds thin out over a couple of seconds
    }
    clouds = clouds.filter((c) => now - c.born < c.life && fadeOut > 0);
    if (clouds.length || drawn) {
      ctx.clearRect(0, 0, w, h);
      for (const c of clouds) {
        const t = (now - c.born) / c.life;
        c.x += c.vx * dt; c.y += c.vy * dt; c.rot += c.spin * dt;
        const size = c.size0 + (c.size1 - c.size0) * (1 - Math.pow(1 - t, 2));  // swells, then eases
        ctx.globalAlpha = c.alpha * Math.sin(Math.PI * Math.min(1, t * 1.15)) * fadeOut;  // fade in and out
        ctx.save();
        ctx.translate(c.x * Q, c.y * Q);
        ctx.rotate(c.rot);
        ctx.drawImage(c.img, -size * Q / 2, -size * Q / 2, size * Q, size * Q);
        ctx.restore();
      }
      ctx.globalAlpha = 1;
      drawn = clouds.length > 0;
    }
    if (menu.classList.contains("gone") && !clouds.length) return;  // on the map: stop for good
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
})();
