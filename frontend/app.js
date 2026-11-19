// Model output is only ever written with textContent, never innerHTML.
const $ = (id) => document.getElementById(id);

function setText(id, text) {
  $(id).textContent = text;
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

function busy(button, label, on) {
  if (!button.dataset.label) button.dataset.label = button.textContent;
  button.disabled = on;
  button.textContent = on ? label : button.dataset.label;
}

function clearResult() {
  setText("error", "");
  setText("answer", "");
  $("result-title").hidden = true;
  $("citations-box").hidden = true;
  $("trace-box").hidden = true;
}

function cell(text) {
  const td = document.createElement("td");
  td.textContent = text;
  return td;
}

function renderResult(title, data) {
  setText("result-title", title);
  $("result-title").hidden = false;
  setText("answer", data.answer);

  const list = $("citations");
  list.replaceChildren();
  for (const c of data.citations) {
    if (!c.verified || !c.url.startsWith("https://github.com/")) continue;
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.href = c.url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.textContent = `${c.path}:${c.start}-${c.end}`;
    li.appendChild(a);
    list.appendChild(li);
  }
  $("citations-box").hidden = list.children.length === 0;

  const t = data.trace;
  setText(
    "trace-summary",
    `${t.llm_calls} model calls, ${t.tool_calls} tool calls, ` +
      `${t.tokens_in} tokens in, ${t.tokens_out} tokens out, ` +
      `${(t.latency_ms / 1000).toFixed(1)} s, estimated cost $${t.est_cost_usd.toFixed(4)}`
  );
  const body = $("trace-steps");
  body.replaceChildren();
  for (const s of t.steps) {
    const tr = document.createElement("tr");
    const args = Object.keys(s.args || {}).length ? JSON.stringify(s.args) : "";
    tr.append(cell(s.agent), cell(`${s.kind}: ${s.name}`), cell(`${args} ${s.preview}`.trim()));
    body.appendChild(tr);
  }
  $("trace-box").hidden = false;
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
  busy(button, label, true);
  try {
    await fn();
  } catch (e) {
    setText("error", e.message);
  } finally {
    busy(button, "", false);
  }
}

$("tab-ask").addEventListener("click", () => selectTab("ask"));
$("tab-issue").addEventListener("click", () => selectTab("issue"));

$("index-btn").addEventListener("click", () => {
  setText("status", "");
  run($("index-btn"), "Indexing...", async () => {
    const d = await post("/index", { repo_url: $("repo-url").value.trim() });
    setText(
      "status",
      `Indexed ${d.repo_name}: ${d.files_indexed} files, ${d.chunks_indexed} chunks in ${d.seconds} s.`
    );
    for (const id of ["question", "ask-btn", "issue-url", "issue-btn"]) $(id).disabled = false;
  });
});

$("ask-btn").addEventListener("click", () =>
  run($("ask-btn"), "Thinking...", async () => {
    const data = await post("/ask", { question: $("question").value, mode: $("mode").value });
    renderResult("Answer", data);
  })
);

$("issue-btn").addEventListener("click", () =>
  run($("issue-btn"), "Planning...", async () => {
    const data = await post("/issue", { issue_url: $("issue-url").value.trim() });
    renderResult("Fix Plan", data);
  })
);

$("question").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !$("ask-btn").disabled) $("ask-btn").click();
});
