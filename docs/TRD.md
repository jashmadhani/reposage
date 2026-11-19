# RepoSage v2: Technical Design

One FastAPI container on Cloud Run holds the index in memory and runs a three agent Google ADK pipeline over three retrieval tools.

## Request flow

```
Browser ──> FastAPI (/ask or /issue) ──> Researcher ⇄ tools (search_code, read_file_lines, list_files) over FAISS
                                              │ evidence
                                              ▼
                                   LoopAgent(max 2): Writer ⇄ Reviewer
                                              │ approved draft + trace
Browser <──────────────────────────── FastAPI
```

## Stack

| Layer | Choice |
| --- | --- |
| API | FastAPI, Uvicorn, Python 3.12 |
| Agents | `google-adk` (`SequentialAgent`, `LoopAgent`, `LlmAgent`, `exit_loop`) |
| LLM | `gemini-2.5-flash` via `GOOGLE_API_KEY` |
| Embeddings | `gemini-embedding-001`, 768 dims, task types `RETRIEVAL_DOCUMENT` / `RETRIEVAL_QUERY` (ADR 0002) |
| Vector store | FAISS `IndexFlatIP` on L2 normalised vectors (cosine) |
| Hosting | Cloud Run, `asia-south1`, `--max-instances 1`, 2 GiB (ADR 0003) |

## Modules (`backend/`)

| File | Responsibility | Status |
| --- | --- | --- |
| `repo_loader.py` | Clone and filter files; add GitHub URL validation | v1, small change |
| `chunker.py` | `Chunk(path, start_line, end_line, symbol, text)`; AST and window chunking; `citation`, `embedding_text()` | Drafted |
| `embeddings.py` | `GeminiEmbedder`, `LocalEmbedder`, `get_embedder()`, `set_embedder()` | Drafted |
| `vector_store.py` | `RepoIndex(repo_name, files)`, `.search(query, k=6, min_score=0.30)`, `.read_lines(path, start, end)`; module `build()`, `current()` | Drafted |
| `agent/tools.py` | ADK function tools over `vector_store.current()` | To do |
| `agent/pipeline.py` | Build agents, run with `InMemoryRunner`, collect Trace | To do |
| `issues.py` | Fetch issue title and body from GitHub REST (public, no auth) | To do |
| `limits.py` | In memory per IP sliding window limiter | To do |
| `rag_pipeline.py` | `simple` mode on top of `vector_store` | Rework |
| `main.py` | Routes, static frontend, limits | Rework |

Drafted files exist on `v2-agents` but are not yet covered by tests; Task 1 of the plan verifies them.

## Agents

| Agent | Instruction gist | Tools | `output_key` |
| --- | --- | --- | --- |
| Researcher | Gather Evidence; call `search_code` with 2 to 4 different queries, `read_file_lines` to confirm; list each excerpt with `path:start-end` | search_code, read_file_lines, list_files | `evidence` |
| Writer | Answer (or Fix Plan in issue mode) using only `{evidence}`; every claim ends with a Citation; address `{review?}` if present | none | `draft` |
| Reviewer | For each Citation in `{draft}`, call `read_file_lines` and check the claim; if all hold call `exit_loop`; else list unsupported claims | read_file_lines, exit_loop | `review` |

Note: ADK treats `{name}` in instructions as state templates; never put literal braces in instruction text. `{review?}` is optional.

After the run, the API parses Citations from `draft` with the regex `([\w./-]+):(\d+)-(\d+)`, keeps those whose path exists in the index, and builds GitHub links `https://github.com/<owner>/<name>/blob/HEAD/<path>#L<start>-L<end>`.

## Tools

| Tool | Signature | Returns |
| --- | --- | --- |
| `search_code` | `(query: str) -> str` | Up to 6 Chunks, each `### path:start-end (symbol) score=0.xx` then the text; "No relevant code found." if none pass the floor |
| `read_file_lines` | `(path: str, start: int, end: int) -> str` | Numbered lines, max 120 lines; error string for unknown path |
| `list_files` | `(pattern: str = "*") -> str` | Matching paths via `fnmatch`, max 200 |

Every tool output is truncated to 6,000 characters.

## API

| Method | Path | Body | Returns |
| --- | --- | --- | --- |
| POST | `/index` | `{repo_url}` | `{status, repo_name, files_indexed, chunks_indexed, seconds}` |
| POST | `/ask` | `{question, mode: "agent" or "simple"}` | `{answer, citations: [{path, start, end, url, verified}], trace}` |
| POST | `/issue` | `{issue_url}` | Same shape; `answer` is the Fix Plan |
| GET | `/health` | none | `{ok, repo}` |
| GET | `/` | none | Frontend (static) |

Errors: `{status: "error", message}` with 400 (bad input), 409 (nothing indexed or issue from another repository), 429 (limit), 502 (upstream Gemini or GitHub failure).

**Trace:** `{steps: [{agent, kind: "llm" or "tool", name, args, preview}], llm_calls, tool_calls, tokens_in, tokens_out, latency_ms, est_cost_usd}`. Tokens from each event's `usage_metadata` (`prompt_token_count`, `candidates_token_count`). Cost uses constants in `pipeline.py` (price per million input and output tokens), labelled "estimate".

## Limits

`limits.py`: dict of IP to deque of timestamps; `check(ip, bucket, max_per_hour)`. Buckets: `ask` 60, `index` 10. IP from `X-Forwarded-For` first value (Cloud Run), else `request.client.host`. Repository cap: 500 files after filtering.

## Testing

- `tests/fakes.py`: `FakeEmbedder` (deterministic vectors from hashed tokens, normalised) and a `FakeLlm(BaseLlm)` that returns scripted responses, so ADK runs offline.
- Unit: chunker line numbers and symbols; store search ranking and floor; tools output format and truncation; citation parsing and GitHub links; limiter.
- API: `/index` with a local fixture repo (monkeypatch clone), `/ask` simple and agent with fakes, `/issue` with monkeypatched fetch, 429 path.
- Eval (F14): `eval/reposage.evalset.json`, 10 questions about RepoSage itself with expected cited files; run manually with a real key.

## Deploy

Dockerfile on `python:3.12-slim`, installs `git`, copies `backend/` and `frontend/`, runs `uvicorn main:app --host 0.0.0.0 --port $PORT`. From Cloud Shell:

```bash
gcloud run deploy reposage --source . --region asia-south1 \
  --max-instances 1 --memory 2Gi --timeout 120 --allow-unauthenticated \
  --set-env-vars GOOGLE_API_KEY=<key>
```

## Security

Key only via env var; secret shaped files excluded before indexing; only `https://github.com/` URLs accepted; clone depth 1; size caps kept; HTML escaped in the frontend (answers are model output).

## Known limitations

In memory index lost on restart; one Repository at a time; single instance; public endpoint without auth; only Python gets AST chunking.
