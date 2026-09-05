const API = "http://127.0.0.1:8000";

const repoInput = document.getElementById("repo-url");
const indexBtn = document.getElementById("index-btn");
const questionInput = document.getElementById("question");
const askBtn = document.getElementById("ask-btn");
const statusEl = document.getElementById("status");
const errorEl = document.getElementById("error");
const answerEl = document.getElementById("answer");
const sourcesBox = document.getElementById("sources-box");
const sourcesEl = document.getElementById("sources");

function clearMessages() {
  errorEl.textContent = "";
  statusEl.textContent = "";
}

async function postJSON(path, body) {
  const response = await fetch(API + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return response.json();
}

indexBtn.addEventListener("click", async () => {
  const repoUrl = repoInput.value.trim();
  if (!repoUrl) {
    errorEl.textContent = "Enter a repository URL.";
    return;
  }

  clearMessages();
  indexBtn.disabled = true;
  statusEl.textContent =
    "Indexing... the first run also downloads the embedding model, so this can take a few minutes.";

  try {
    const data = await postJSON("/index", { repo_url: repoUrl });
    if (data.status === "error") {
      errorEl.textContent = data.message;
      statusEl.textContent = "";
    } else {
      statusEl.textContent = `Indexed ${data.files_indexed} files from ${data.repo_name}.`;
      questionInput.disabled = false;
      askBtn.disabled = false;
    }
  } catch (e) {
    errorEl.textContent = "Could not reach the backend. Is it running on port 8000?";
    statusEl.textContent = "";
  }

  indexBtn.disabled = false;
});

askBtn.addEventListener("click", async () => {
  const question = questionInput.value.trim();
  if (!question) {
    errorEl.textContent = "Enter a question.";
    return;
  }

  clearMessages();
  askBtn.disabled = true;
  answerEl.textContent = "";
  sourcesBox.hidden = true;
  statusEl.textContent = "Thinking...";

  try {
    const data = await postJSON("/ask", { question });
    statusEl.textContent = "";

    if (data.status === "error") {
      errorEl.textContent = data.message;
    } else {
      answerEl.textContent = data.answer;
      sourcesEl.innerHTML = "";
      data.sources.forEach((path) => {
        const li = document.createElement("li");
        li.textContent = path;
        sourcesEl.appendChild(li);
      });
      sourcesBox.hidden = false;
    }
  } catch (e) {
    statusEl.textContent = "";
    errorEl.textContent = "Could not reach the backend. Is it running on port 8000?";
  }

  askBtn.disabled = false;
});
