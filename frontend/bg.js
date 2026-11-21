// GPU dither background: a GLSL fragment shader computes a slow, domain-warped
// colour flow and quantises it with an 8x8 ordered (Bayer) dither on a 3px grid,
// into five stops read from --dither-c0 .. --dither-c4 (navy, blue, violet,
// yellow, white). A few soft white blobs roam through it. Everything is a sum of
// slow sines, so the motion is continuous and nothing pulses. The colours fade
// toward white behind the header and headline so text stays readable. The
// pointer pushes the colour toward the bright end. window.reposageBg.freeze()
// holds a still frame (used once a repository link is submitted). Plain WebGL.
(() => {
  const canvas = document.getElementById("bg");
  if (!canvas) return;
  const gl = canvas.getContext("webgl", { alpha: false, antialias: false });
  if (!gl) return;

  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)");
  const POINTER_R = 220; // CSS px

  const VERT = "attribute vec2 p; void main(){ gl_Position = vec4(p, 0.0, 1.0); }";
  const FRAG = `
precision highp float;
uniform float uDpr, uTime, uPtrOn;
uniform vec2 uSize, uPtr;
uniform vec3 uC0, uC1, uC2, uC3, uC4;
const float CELL = 3.0;
const float PR = ${POINTER_R.toFixed(1)};

// Ordered dither thresholds in [0, 1): 8x8 Bayer built from 2x2 steps.
float bayer2(vec2 a) { a = floor(a); return fract(a.x / 2.0 + a.y * a.y * 0.75); }
float bayer4(vec2 a) { return bayer2(0.5 * a) * 0.25 + bayer2(a); }
float bayer8(vec2 a) { return bayer4(0.5 * a) * 0.25 + bayer2(a); }

vec3 stop(float i) {
  if (i < 0.5) return uC0;
  if (i < 1.5) return uC1;
  if (i < 2.5) return uC2;
  if (i < 3.5) return uC3;
  return uC4;
}

void main() {
  vec2 frag = gl_FragCoord.xy / uDpr;           // CSS px, origin bottom left
  vec2 cell = floor(frag / CELL);
  vec2 c = (cell + 0.5) * CELL;
  vec2 uv = c / uSize;
  float aspect = uSize.x / uSize.y;
  float yTop = 1.0 - uv.y;
  float t = uTime * 0.32;

  // A warped flow: the coordinates are pushed around twice by slow waves, then a
  // few more waves are summed. Slow clocks keep the motion fluid.
  vec2 p = vec2(uv.x * aspect, uv.y) * 2.3;
  vec2 q = vec2(sin(p.y * 1.3 + t * 0.8) + sin(p.x * 0.9 - t * 0.6),
                cos(p.x * 1.1 - t * 0.7) + cos(p.y * 0.8 + t * 0.5));
  p += 0.55 * q;
  vec2 r = vec2(sin(p.y * 1.1 - t * 0.5), cos(p.x * 1.2 + t * 0.45));
  p += 0.35 * r;
  float v = 0.5 + 0.42 * (0.5 * sin(p.x * 1.2 + t * 0.3) + 0.35 * sin(p.y * 1.4 - t * 0.25) + 0.25 * sin((p.x + p.y) * 0.9 + t * 0.2)) / 0.55;
  v = smoothstep(0.05, 0.95, v);

  // The pointer pulls nearby colour toward the bright end.
  if (uPtrOn > 0.01) {
    vec2 d = vec2(c.x - uPtr.x, yTop * uSize.y - uPtr.y);
    float w = 1.0 - dot(d, d) / (PR * PR);
    if (w > 0.0) v = min(1.0, v + uPtrOn * w * w * 0.4);
  }

  // Quantise across the five stops with the ordered dither.
  float s = v * 4.0;
  float i = floor(s);
  if (s - i > bayer8(cell)) i += 1.0;
  vec3 col = stop(min(i, 4.0));

  // A little white roaming between them: three soft blobs on slow looping paths.
  float white = 0.0;
  for (int k = 0; k < 3; k++) {
    float kf = float(k);
    vec2 bp = vec2(0.5 + 0.42 * sin(t * (0.43 + 0.11 * kf) + kf * 2.1),
                   0.5 + 0.36 * sin(t * (0.31 + 0.09 * kf) + kf * 1.3 + 0.7));
    vec2 dd = vec2((uv.x - bp.x) * aspect, uv.y - bp.y);
    white += exp(-dot(dd, dd) / 0.014);
  }
  if (clamp(white, 0.0, 1.0) * 0.95 > bayer8(cell + vec2(3.0, 5.0))) col = uC4;

  // Calm the colour behind the header and the headline so text stays readable.
  float colx = 1.0 - smoothstep(0.10, 0.36, abs(uv.x - 0.5));
  float hero = 1.0 - smoothstep(0.20, 0.36, yTop);
  float topband = 1.0 - smoothstep(0.06, 0.13, yTop);
  float calm = max(max(colx * 0.18, colx * hero), topband * 0.9);
  col = mix(col, vec3(1.0), calm * 0.78);

  gl_FragColor = vec4(col, 1.0);
}`;

  function compile(type, src) {
    const sh = gl.createShader(type);
    gl.shaderSource(sh, src);
    gl.compileShader(sh);
    if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
      console.warn("bg shader:", gl.getShaderInfoLog(sh));
      return null;
    }
    return sh;
  }
  const vs = compile(gl.VERTEX_SHADER, VERT);
  const fs = compile(gl.FRAGMENT_SHADER, FRAG);
  if (!vs || !fs) return;
  const prog = gl.createProgram();
  gl.attachShader(prog, vs);
  gl.attachShader(prog, fs);
  gl.linkProgram(prog);
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) return;
  gl.useProgram(prog);

  // One triangle that covers the whole canvas.
  const buf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buf);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(prog, "p");
  gl.enableVertexAttribArray(loc);
  gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);

  const U = {};
  for (const n of ["uDpr", "uTime", "uPtrOn", "uSize", "uPtr", "uC0", "uC1", "uC2", "uC3", "uC4"]) U[n] = gl.getUniformLocation(prog, n);

  let W = 0, H = 0, dpr = 1;
  let raf = 0, lastT = 0, frozen = false;
  const ptr = { tx: -9999, ty: -9999, x: -9999, y: -9999, on: 0, target: 0 };

  function hexToRgb(hex) {
    let h = String(hex).trim().replace("#", "");
    if (h.length === 3) h = h.split("").map((c) => c + c).join("");
    const n = parseInt(h, 16);
    return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
  }

  // Colours come from CSS so the theme decides them.
  function readPalette() {
    const cs = getComputedStyle(document.documentElement);
    const defaults = ["#0a0a78", "#2430ff", "#9a4dff", "#ffe83a", "#ffffff"];
    defaults.forEach((fb, n) => gl.uniform3fv(U["uC" + n], hexToRgb(cs.getPropertyValue("--dither-c" + n) || fb)));
  }

  function resize() {
    W = window.innerWidth;
    H = window.innerHeight;
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    canvas.style.width = W + "px";
    canvas.style.height = H + "px";
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.uniform1f(U.uDpr, dpr);
    gl.uniform2f(U.uSize, W, H);
    readPalette();
    draw(6, 0);
  }

  function draw(t, dt) {
    // Ease the pointer toward its target; fade its influence in and out.
    const k = 1 - Math.exp(-dt * 8);
    if (ptr.x < -9000) { ptr.x = ptr.tx; ptr.y = ptr.ty; }
    ptr.x += (ptr.tx - ptr.x) * k;
    ptr.y += (ptr.ty - ptr.y) * k;
    ptr.on += (ptr.target - ptr.on) * (1 - Math.exp(-dt * 5));

    gl.uniform1f(U.uTime, t);
    gl.uniform1f(U.uPtrOn, ptr.on);
    gl.uniform2f(U.uPtr, ptr.x, ptr.y);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }

  function loop(now) {
    raf = requestAnimationFrame(loop);
    const dt = Math.min(0.1, (now - (lastT || now)) / 1000);
    lastT = now;
    draw(now / 1000, dt); // one draw per display frame, so up to 120 fps
  }

  function start() {
    cancelAnimationFrame(raf);
    lastT = 0;
    if (frozen || reduceMotion.matches || document.hidden) {
      ptr.target = 0;
      ptr.on = 0;
      draw(6, 0); // still frame
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

  window.reposageBg = { freeze };
  resize();
  start();
})();
