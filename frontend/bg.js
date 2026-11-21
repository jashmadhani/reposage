// Ordered-dither background: a Bayer 8x8 threshold turns a soft light field into
// very fine square dots (1px), in a three step ramp read from the CSS tokens
// --dither-low / --dither-mid / --dither-high. The field is a single soft dome of
// light rising from the bottom edge. It sways very slowly and nothing pulses.
// Dots under the pointer brighten steadily. window.reposageBg.freeze() holds a
// still frame (used once a repository link is submitted). Pure canvas 2D.
(() => {
  const canvas = document.getElementById("bg");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const DOT = 1; // CSS pixels per dot
  const FPS = 120; // runs at the display's refresh rate, up to 120
  const INTENSITY = 1.0;
  const POINTER_R = 190; // px
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)");
  const darkQuery = matchMedia("(prefers-color-scheme: dark)");

  // 8x8 Bayer matrix as thresholds in (0, 1).
  const BAYER = new Float32Array(64);
  for (let y = 0; y < 8; y++) {
    for (let x = 0; x < 8; x++) {
      const a = x ^ y;
      let r = 0;
      for (let i = 0; i < 3; i++) r = (r << 2) | (((y >> (2 - i)) & 1) << 1) | ((a >> (2 - i)) & 1);
      BAYER[y * 8 + x] = (r + 0.5) / 64;
    }
  }

  let cw = 0, ch = 0, W = 0, H = 0;
  let img = null, out = null;
  let pal = [0, 0, 0, 0];
  let raf = 0, lastDraw = 0, lastT = 0, frozen = false;
  const ptr = { tx: -9999, ty: -9999, x: -9999, y: -9999, on: 0, target: 0 };

  function hexToRgb(hex) {
    let h = String(hex).trim().replace("#", "");
    if (h.length === 3) h = h.split("").map((c) => c + c).join("");
    const n = parseInt(h, 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }

  // Colors come from CSS so the theme decides them.
  function readPalette() {
    const cs = getComputedStyle(document.documentElement);
    const pack = (name, fallback) => {
      const [r, g, b] = hexToRgb(cs.getPropertyValue(name) || fallback);
      return (255 << 24) | (b << 16) | (g << 8) | r; // ABGR for a little endian Uint32 view
    };
    pal = [0, pack("--dither-low", "#a7ece0"), pack("--dither-mid", "#2bb5a5"), pack("--dither-high", "#0d6e66")];
  }

  function resize() {
    W = window.innerWidth;
    H = window.innerHeight;
    cw = Math.ceil(W / DOT);
    ch = Math.ceil(H / DOT);
    canvas.width = cw;
    canvas.height = ch;
    canvas.style.width = W + "px";
    canvas.style.height = H + "px";
    canvas.style.imageRendering = "pixelated";
    img = ctx.createImageData(cw, ch);
    out = new Uint32Array(img.data.buffer);
    readPalette();
    draw(4, 0);
  }

  function draw(t, dt) {
    // Ease the pointer toward its target; fade its influence in and out.
    const k = 1 - Math.exp(-dt * 8);
    if (ptr.x < -9000) { ptr.x = ptr.tx; ptr.y = ptr.ty; }
    ptr.x += (ptr.tx - ptr.x) * k;
    ptr.y += (ptr.ty - ptr.y) * k;
    ptr.on += (ptr.target - ptr.on) * (1 - Math.exp(-dt * 5));

    // One dome of light on the bottom edge, swaying very slowly side to side.
    const cx = W * (0.5 + 0.04 * Math.sin(t * 0.09));
    const rx = W * 0.52;
    const ry = H * 0.85;
    const R2 = POINTER_R * POINTER_R;
    const pOn = ptr.on;
    const pcx = ptr.x, pcy = ptr.y;

    let i = 0;
    for (let y = 0; y < ch; y++) {
      const py = y * DOT;
      const ny = (py - H * 1.02) / ry;
      const ny2 = ny * ny;
      const dy = py - pcy;
      const brow = (y & 7) * 8;
      for (let x = 0; x < cw; x++, i++) {
        const px = x * DOT;
        const nx = (px - cx) / rx;
        const g = 1 - (nx * nx + ny2);
        let f = g > 0 ? g * Math.sqrt(g) * 1.1 : 0;

        if (pOn > 0.01) {
          const dx = px - pcx;
          const d2 = dx * dx + dy * dy;
          if (d2 < R2) {
            const w = 1 - d2 / R2;
            f += pOn * w * w * 0.55;
          }
        }

        f *= INTENSITY;
        if (f <= 0) { out[i] = 0; continue; }
        if (f > 1) f = 1;
        const s = f * 3;
        let lvl = s | 0;
        if (s - lvl > BAYER[brow + (x & 7)]) lvl++;
        out[i] = lvl === 0 ? 0 : pal[lvl > 3 ? 3 : lvl];
      }
    }
    ctx.putImageData(img, 0, 0);
  }

  function loop(now) {
    raf = requestAnimationFrame(loop);
    if (now - lastDraw < 1000 / FPS - 2) return;
    const dt = Math.min(0.1, (now - (lastT || now)) / 1000);
    lastDraw = now;
    lastT = now;
    draw(now / 1000, dt);
  }

  function start() {
    cancelAnimationFrame(raf);
    lastT = 0;
    if (frozen || reduceMotion.matches || document.hidden) {
      ptr.target = 0;
      ptr.on = 0;
      draw(4, 0); // still frame
      return;
    }
    raf = requestAnimationFrame(loop);
  }

  // Holds a still frame and ignores the pointer from now on.
  function freeze() {
    frozen = true;
    ptr.target = 0;
    start();
  }

  window.addEventListener("pointermove", (e) => {
    if (frozen || reduceMotion.matches) return;
    ptr.tx = e.clientX;
    ptr.ty = e.clientY;
    ptr.target = 1;
  }, { passive: true });
  document.addEventListener("pointerleave", () => { ptr.target = 0; });
  window.addEventListener("blur", () => { ptr.target = 0; });
  window.addEventListener("pointerup", (e) => { if (e.pointerType !== "mouse") ptr.target = 0; });

  let resizeTimer = 0;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => { resize(); start(); }, 120);
  });
  document.addEventListener("visibilitychange", start);
  reduceMotion.addEventListener("change", start);
  darkQuery.addEventListener("change", () => { readPalette(); draw(4, 0); });

  window.reposageBg = { freeze };
  resize();
  start();
})();
