// Model output is only ever written with textContent and createElement,
// never innerHTML, so nothing the model says can become markup.
const $ = (id) => document.getElementById(id);
const CITE_RE = /([\w./-]+):(\d+)-(\d+)/g;

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

// Disables a button and shows "Label... 12s" while a request runs.
function startBusy(button, label) {
  if (!button.dataset.label) button.dataset.label = button.textContent;
  const started = Date.now();
  button.disabled = true;
  const tick = () => {
    button.textContent = `${label} ${Math.floor((Date.now() - started) / 1000)}s`;
  };
  tick();
  const timer = setInterval(tick, 1000);
  return () => {
    clearInterval(timer);
    button.textContent = button.dataset.label;
    button.disabled = false;
  };
}

function clearResult() {
  setText("error", "");
  $("result").hidden = true;
  setText("answer", "");
}

function cell(text) {
  const td = document.createElement("td");
  td.textContent = text;
  return td;
}

function chip(label, value) {
  const span = document.createElement("span");
  span.className = "stat";
  const strong = document.createElement("strong");
  strong.textContent = value;
  span.append(strong, document.createTextNode(" " + label));
  return span;
}

// Writes the answer with each verified citation turned into a link.
function renderAnswer(text, citations) {
  const root = $("answer");
  root.replaceChildren();
  const verified = new Map();
  for (const c of citations) {
    if (c.verified && c.url.startsWith("https://github.com/")) {
      verified.set(`${c.path}:${c.start}-${c.end}`, c.url);
    }
  }
  let last = 0;
  for (const m of text.matchAll(CITE_RE)) {
    const url = verified.get(m[0]);
    if (!url) continue;
    root.append(document.createTextNode(text.slice(last, m.index)));
    const a = document.createElement("a");
    a.className = "cite";
    a.href = url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.textContent = m[0];
    root.append(a);
    last = m.index + m[0].length;
  }
  root.append(document.createTextNode(text.slice(last)));
}

function renderResult(title, data) {
  setText("result-title", title);
  renderAnswer(data.answer, data.citations);

  const list = $("citations");
  list.replaceChildren();
  const seen = new Set();
  for (const c of data.citations) {
    const key = `${c.path}:${c.start}-${c.end}`;
    if (!c.verified || !c.url.startsWith("https://github.com/") || seen.has(key)) continue;
    seen.add(key);
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.href = c.url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.textContent = key;
    li.appendChild(a);
    list.appendChild(li);
  }
  $("citations-box").hidden = list.children.length === 0;

  const t = data.trace;
  const chips = $("trace-chips");
  chips.replaceChildren(
    chip("model calls", t.llm_calls),
    chip("tool calls", t.tool_calls),
    chip("tokens in", t.tokens_in.toLocaleString()),
    chip("tokens out", t.tokens_out.toLocaleString()),
    chip("seconds", (t.latency_ms / 1000).toFixed(1)),
    chip("est. cost", "$" + t.est_cost_usd.toFixed(4))
  );
  const body = $("trace-steps");
  body.replaceChildren();
  for (const s of t.steps) {
    const tr = document.createElement("tr");
    tr.className = "agent-" + String(s.agent).replace(/[^a-z]/gi, "");
    const args = Object.keys(s.args || {}).length ? JSON.stringify(s.args) : "";
    tr.append(cell(s.agent), cell(`${s.kind}: ${s.name}`), cell(`${args} ${s.preview}`.trim()));
    body.appendChild(tr);
  }
  $("trace-box").hidden = false;
  $("result").hidden = false;
  $("result").scrollIntoView({ behavior: "smooth", block: "start" });
}

function selectTab(name) {
  for (const t of ["ask", "issue"]) {
    const on = t === name;
    $(`tab-${t}`).classList.toggle("active", on);
    $(`tab-${t}`).setAttribute("aria-selected", String(on));
    $(`panel-${t}`).hidden = !on;
  }
}

async function run(button, label, fn) {
  clearResult();
  const stop = startBusy(button, label);
  try {
    await fn();
  } catch (e) {
    setText("error", friendly(e.message));
  } finally {
    stop();
  }
}

$("tab-ask").addEventListener("click", () => selectTab("ask"));
$("tab-issue").addEventListener("click", () => selectTab("issue"));

// Example chips fill an input; they never submit anything.
document.querySelectorAll(".chip").forEach((el) =>
  el.addEventListener("click", () => {
    const input = $(el.dataset.fill);
    if (input.disabled) return;
    input.value = el.dataset.value;
    input.focus();
  })
);

$("index-btn").addEventListener("click", () => {
  setText("status", "");
  run($("index-btn"), "Indexing", async () => {
    const d = await post("/index", { repo_url: $("repo-url").value.trim() });
    setText(
      "status",
      `Indexed ${d.repo_name}: ${d.files_indexed} files, ${d.chunks_indexed} chunks in ${d.seconds} s.`
    );
    for (const id of ["question", "ask-btn", "issue-url", "issue-btn"]) $(id).disabled = false;
    $("step-ask").classList.remove("locked");
    $("lock-note").hidden = true;
    $("question").focus();
  });
});

$("ask-btn").addEventListener("click", () =>
  run($("ask-btn"), "Working", async () => {
    const mode = document.querySelector('input[name="mode"]:checked').value;
    const data = await post("/ask", { question: $("question").value, mode });
    renderResult("Answer", data);
  })
);

$("issue-btn").addEventListener("click", () =>
  run($("issue-btn"), "Planning", async () => {
    const data = await post("/issue", { issue_url: $("issue-url").value.trim() });
    renderResult("Fix Plan", data);
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
  if (e.key === "Enter") $("index-btn").click();
});
$("question").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !$("ask-btn").disabled) $("ask-btn").click();
});
$("issue-url").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !$("issue-btn").disabled) $("issue-btn").click();
});
