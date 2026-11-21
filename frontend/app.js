// Model output is only ever written with textContent and createElement,
// never innerHTML, so nothing the model says can become markup.
const $ = (id) => document.getElementById(id);
const CITE_RE = /([\w./-]+):(\d+)-(\d+)/g;
const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)");

function setText(id, text) {
  $(id).textContent = text;
}

function friendly(message) {
  const m = String(message || "");
  if (/RESOURCE_EXHAUSTED|\b429\b/.test(m) && !/limit reached/i.test(m)) {
    return "The model is rate limited right now. Wait a minute and try again.";
  }
  if (/UNAVAILABLE|\b503\b/.test(m)) {
    return "The model is busy. Try again in a moment.";
  }
  return m.length > 300 ? m.slice(0, 300) + "..." : m;
}

async function post(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.message || `Request failed (${res.status})`);
  return data;
}

/* ---------- pixel grid loader ---------- */
// 3x3 grid; the wavefront is a chevron: delay = (col + |row - 1|) * 90ms.
function makeLoader(labels) {
  const root = document.createElement("div");
  root.className = "loader";
  root.setAttribute("role", "status");

  const grid = document.createElement("span");
  grid.className = "pg";
  grid.setAttribute("aria-hidden", "true");
  for (let r = 0; r < 3; r++) {
    for (let c = 0; c < 3; c++) {
      const px = document.createElement("i");
      px.style.setProperty("--d", `${(c + Math.abs(r - 1)) * 90}ms`);
      grid.appendChild(px);
    }
  }
  const label = document.createElement("span");
  label.className = "loader-label";
  const time = document.createElement("span");
  time.className = "loader-time";
  root.append(grid, label, time);

  const started = Date.now();
  const tick = () => {
    const s = Math.floor((Date.now() - started) / 1000);
    time.textContent = `${s}s`;
    label.textContent = labels[Math.min(labels.length - 1, Math.floor(s / 7))];
  };
  tick();
  const timer = setInterval(tick, 1000);
  return { root, stop: () => { clearInterval(timer); root.remove(); } };
}

// Shows the loader in a slot and locks the button while fn runs.
async function withLoader(slotId, button, labels, fn) {
  const slot = $(slotId);
  const loader = makeLoader(labels);
  slot.replaceChildren(loader.root);
  button.disabled = true;
  try {
    return await fn();
  } finally {
    loader.stop();
    button.disabled = false;
  }
}

/* ---------- text reveal ---------- */
function reveal(container) {
  container.classList.remove("is-shown");
  requestAnimationFrame(() => requestAnimationFrame(() => container.classList.add("is-shown")));
}

function revealLine(el, i) {
  el.classList.add("t-stagger-line");
  el.style.setProperty("--i", String(Math.min(i, 14)));
}

/* ---------- tabs sliding ---------- */
const tabs = $("tab-ask").parentElement;
const pill = tabs.querySelector(".t-tabs-pill");

function movePill(tab, animate) {
  if (!animate) pill.style.transition = "none";
  pill.style.width = tab.offsetWidth + "px";
  pill.style.transform = `translateX(${tab.offsetLeft}px)`;
  if (!animate) {
    void pill.offsetWidth;
    pill.style.transition = "";
  }
}

function selectTab(name, animate = true) {
  const order = ["ask", "issue"];
  const prev = order.find((t) => $(`tab-${t}`).getAttribute("aria-selected") === "true");
  for (const t of order) {
    const on = t === name;
    $(`tab-${t}`).setAttribute("aria-selected", String(on));
    $(`tab-${t}`).tabIndex = on ? 0 : -1;
    $(`panel-${t}`).hidden = !on;
  }
  $(`panel-${name}`).style.setProperty("--dir", order.indexOf(name) > order.indexOf(prev) ? "14px" : "-14px");
  movePill($(`tab-${name}`), animate);
}

$("tab-ask").addEventListener("click", () => selectTab("ask"));
$("tab-issue").addEventListener("click", () => selectTab("issue"));
tabs.addEventListener("keydown", (e) => {
  const order = ["ask", "issue"];
  const i = order.indexOf(document.activeElement.id.replace("tab-", ""));
  if (i < 0) return;
  let n = i;
  if (e.key === "ArrowRight") n = (i + 1) % 2;
  else if (e.key === "ArrowLeft") n = (i + 1) % 2;
  else if (e.key === "Home") n = 0;
  else if (e.key === "End") n = 1;
  else return;
  e.preventDefault();
  selectTab(order[n]);
  $(`tab-${order[n]}`).focus();
});
const current = () => document.querySelector('.t-tab[aria-selected="true"]');
window.addEventListener("resize", () => movePill(current(), false));
if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => movePill(current(), false));

/* ---------- reasoning stream ---------- */
const LINE_H = 26;
let reasonTimer = 0;

function stepLabel(s) {
  if (s.kind === "tool") {
    const a = s.args || {};
    const hint = a.query || a.path || a.file_path || "";
    return `${s.name}${hint ? " " + String(hint).slice(0, 48) : ""}`;
  }
  return s.preview || s.name;
}

function playReasoning(steps) {
  clearInterval(reasonTimer);
  const text = $("reason-text");
  const scroll = $("reason-scroll");
  const box = $("reason");
  text.replaceChildren();
  scroll.style.transition = "none";
  scroll.style.transform = "translateY(0)";
  if (!steps.length) { box.hidden = true; return; }
  box.hidden = false;

  const build = (s) => {
    const line = document.createElement("span");
    line.className = "rline";
    const who = document.createElement("b");
    who.className = String(s.agent).replace(/[^a-z]/gi, "").toLowerCase();
    who.textContent = s.agent;
    const em = document.createElement("em");
    em.textContent = stepLabel(s).replace(/\s+/g, " ");
    line.append(who, em);
    return line;
  };

  const viewH = box.clientHeight || 108;
  const place = (n) => `translateY(${Math.min(0, viewH - LINE_H * (n + 1) - 14)}px)`;

  if (reduceMotion.matches) {
    steps.forEach((s) => text.appendChild(build(s)));
    scroll.style.transform = place(steps.length - 1);
    return;
  }

  const stepMs = Math.max(120, Math.min(840, 9000 / steps.length));
  let n = 0;
  const next = () => {
    if (n >= steps.length) { clearInterval(reasonTimer); return; }
    text.appendChild(build(steps[n]));
    scroll.style.transition = `transform ${Math.min(500, stepMs)}ms var(--reason-ease)`;
    scroll.style.transform = place(n);
    n++;
  };
  next();
  reasonTimer = setInterval(next, stepMs);
}

/* ---------- rendering ---------- */
function cell(text) {
  const td = document.createElement("td");
  td.textContent = text;
  return td;
}

function stat(label, value) {
  const span = document.createElement("span");
  span.className = "stat";
  const strong = document.createElement("strong");
  strong.textContent = value;
  span.append(strong, document.createTextNode(" " + label));
  return span;
}

// Writes the answer line by line, each verified citation turned into a link.
function renderAnswer(text, citations) {
  const root = $("answer");
  root.replaceChildren();
  root.classList.add("t-stagger");
  const verified = new Map();
  for (const c of citations) {
    if (c.verified && c.url.startsWith("https://github.com/")) {
      verified.set(`${c.path}:${c.start}-${c.end}`, c.url);
    }
  }
  text.split("\n").forEach((line, i) => {
    const div = document.createElement("div");
    div.className = "ln";
    revealLine(div, i);
    let last = 0;
    for (const m of line.matchAll(CITE_RE)) {
      const url = verified.get(m[0]);
      if (!url) continue;
      div.append(document.createTextNode(line.slice(last, m.index)));
      const a = document.createElement("a");
      a.className = "cite";
      a.href = url;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.textContent = m[0];
      div.append(a);
      last = m.index + m[0].length;
    }
    div.append(document.createTextNode(line.slice(last)));
    root.append(div);
  });
  reveal(root);
}

function renderResult(title, data) {
  setText("result-title", title);
  renderAnswer(data.answer, data.citations);

  const list = $("citations");
  list.replaceChildren();
  const seen = new Set();
  let i = 0;
  for (const c of data.citations) {
    const key = `${c.path}:${c.start}-${c.end}`;
    if (!c.verified || !c.url.startsWith("https://github.com/") || seen.has(key)) continue;
    seen.add(key);
    const li = document.createElement("li");
    revealLine(li, i++);
    const a = document.createElement("a");
    a.href = c.url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.textContent = key;
    li.appendChild(a);
    list.appendChild(li);
  }
  $("citations-box").hidden = list.children.length === 0;
  reveal(list);

  const t = data.trace;
  $("trace-chips").replaceChildren(
    stat("model calls", t.llm_calls),
    stat("tool calls", t.tool_calls),
    stat("tokens in", t.tokens_in.toLocaleString()),
    stat("tokens out", t.tokens_out.toLocaleString()),
    stat("seconds", (t.latency_ms / 1000).toFixed(1)),
    stat("est. cost", "$" + t.est_cost_usd.toFixed(4))
  );
  const body = $("trace-steps");
  body.replaceChildren();
  for (const s of t.steps) {
    const tr = document.createElement("tr");
    tr.className = "agent-" + String(s.agent).replace(/[^a-z]/gi, "").toLowerCase();
    const args = Object.keys(s.args || {}).length ? JSON.stringify(s.args) : "";
    tr.append(cell(s.agent), cell(`${s.kind}: ${s.name}`), cell(`${args} ${s.preview}`.trim()));
    body.appendChild(tr);
  }
  const nCites = list.children.length;
  setText("announce", `${title} ready, ${nCites} verified citation${nCites === 1 ? "" : "s"}.`);
  $("trace-card").hidden = false;
  $("result").hidden = false;
  playReasoning(t.steps);
  $("result").scrollIntoView({ behavior: reduceMotion.matches ? "auto" : "smooth", block: "start" });
}

function clearResult() {
  clearInterval(reasonTimer);
  setText("error", "");
  setText("announce", "");
  $("result").hidden = true;
  setText("answer", "");
}

async function run(slot, button, labels, fn) {
  clearResult();
  try {
    await withLoader(slot, button, labels, fn);
  } catch (e) {
    setText("error", friendly(e.message));
  }
}

/* ---------- wiring ---------- */
// Example chips fill an input; they never submit anything.
document.querySelectorAll(".chip").forEach((el) =>
  el.addEventListener("click", () => {
    const input = $(el.dataset.fill);
    if (input.disabled) return;
    input.value = el.dataset.value;
    input.focus();
  })
);

const GITHUB_REPO = /^https:\/\/github\.com\/[\w.-]+\/[\w.-]+?(\.git)?\/?$/;

$("repo-url").addEventListener("input", () => setText("index-error", ""));

$("index-btn").addEventListener("click", () => {
  setText("status", "");
  setText("index-error", "");
  const link = $("repo-url").value.trim();
  // Hard stop: nothing is indexed, and no request is sent, without a public GitHub link.
  if (!link) {
    setText("index-error", "No link entered. Paste a public GitHub repository URL above.");
    $("repo-url").focus();
    return;
  }
  if (!GITHUB_REPO.test(link)) {
    setText("index-error", "That is not a GitHub repository link. Use https://github.com/owner/name");
    $("repo-url").focus();
    return;
  }
  // A real link was submitted: hold the background still so only the loader moves.
  if (window.reposageBg) window.reposageBg.freeze();
  run("loader-index", $("index-btn"),
    ["Cloning the repository", "Chunking files by function and class", "Embedding chunks", "Almost there, building the index"],
    async () => {
      const d = await post("/index", { repo_url: link });
      setText("status", `Indexed ${d.repo_name}: ${d.files_indexed} files, ${d.chunks_indexed} chunks in ${d.seconds} s.`);
      for (const id of ["question", "ask-btn", "issue-url", "issue-btn"]) $(id).disabled = false;
      $("step-ask").classList.remove("locked");
      $("lock-note").hidden = true;
      movePill(current(), false);
      $("question").focus();
    });
});

$("ask-btn").addEventListener("click", () =>
  run("loader-ask", $("ask-btn"),
    ["Researcher is searching the code", "Writer is drafting with citations", "Reviewer is re-reading every cited line"],
    async () => {
      const mode = document.querySelector('input[name="mode"]:checked').value;
      renderResult("Answer", await post("/ask", { question: $("question").value, mode }));
    })
);

$("issue-btn").addEventListener("click", () =>
  run("loader-ask", $("issue-btn"),
    ["Reading the issue", "Finding the relevant code", "Drafting the fix plan", "Reviewer is checking citations"],
    async () => {
      renderResult("Fix Plan", await post("/issue", { issue_url: $("issue-url").value.trim() }));
    })
);

$("copy-btn").addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText($("answer").textContent);
    $("copy-btn").textContent = "Copied";
  } catch (e) {
    $("copy-btn").textContent = "Copy failed";
  }
  setTimeout(() => ($("copy-btn").textContent = "Copy"), 1500);
});

$("repo-url").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !$("index-btn").disabled) $("index-btn").click();
  if (e.key === "Escape") { $("repo-url").value = ""; setText("status", ""); }
});
$("question").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !$("ask-btn").disabled) $("ask-btn").click();
});
$("issue-url").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !$("issue-btn").disabled) $("issue-btn").click();
});

// First paint: place the tab pill, then reveal the hero.
selectTab("ask", false);
reveal($("hero"));
