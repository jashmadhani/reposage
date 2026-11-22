# RepoSage

[![tests](https://github.com/jashmadhani/reposage/actions/workflows/ci.yml/badge.svg)](https://github.com/jashmadhani/reposage/actions/workflows/ci.yml)

Point RepoSage at any public GitHub repository. Ask a Question, or paste an Issue and get a Fix Plan. Every claim cites exact lines, and a Reviewer agent re-reads those lines before the answer is shown.

**Live:** https://reposage-983901098678.asia-south1.run.app (Google Cloud Run, Gemini on Vertex AI). Index a small public repository first, such as `https://github.com/pallets/itsdangerous`. It is a free demo with a daily question limit, so it may say "limit reached".

## Watch the walkthrough (2 min 4 s)

<video src="https://github.com/jashmadhani/reposage/raw/main/docs/media/reposage-walkthrough.mp4" poster="https://github.com/jashmadhani/reposage/raw/main/docs/media/reposage-walkthrough-poster.jpg" controls width="100%"></video>

If the player does not load, [open the video file](docs/media/reposage-walkthrough.mp4) directly.

A narrated tour of the current interface, recorded from the live app, with a caption on every step: paste a repository, index it, ask a question, read the answer with its verified citations, open the Trace, and turn an issue into a Fix Plan. The narration is generated offline with the open source Kokoro voice model; nothing in the video is mocked.

## What makes it different

- **Fix Plans.** Paste a GitHub Issue URL from the indexed Repository and get the files and lines to change, ordered steps, tests to update and risks.
- **Verified Citations.** The Writer cites `path:start-end` after each claim. The Reviewer calls a tool to re-read every cited range and either approves the draft or sends back the unsupported claims (at most two rounds). Citations link to the exact lines on GitHub.
- **Trace.** Each response comes with the agent steps, tool calls, tokens, latency and an estimated cost.

## Architecture

```
Browser ──> FastAPI (/ask or /issue) ──> Researcher ⇄ tools (search_code, read_file_lines, list_files) over FAISS
                                              │ evidence
                                              ▼
                                   LoopAgent(max 2): Writer ⇄ Reviewer
                                              │ approved draft + trace
Browser <──────────────────────────── FastAPI
```

Python 3.12, FastAPI, Google ADK (three agents), Gemini (the live demo runs `gemini-3.5-flash-lite` on Vertex AI), Gemini embeddings, FAISS, Cloud Run. The interface is plain HTML, CSS and JavaScript with a WebGL background; model output is written to the page with DOM nodes only, never as HTML. Python files are chunked by top level function and class; other files by 60 line windows with 15 lines of overlap. A `simple` mode (one retrieval plus one model call) is available for speed.

Full design: [`docs/PRD.md`](docs/PRD.md), [`docs/TRD.md`](docs/TRD.md), [`GLOSSARY.md`](GLOSSARY.md).

## Design decisions

- [Three agent ADK pipeline, no Planner](docs/adr/0001-three-agent-adk-pipeline.md)
- [Gemini embeddings by default instead of local sentence-transformers](docs/adr/0002-gemini-embeddings-on-cloud-run.md)
- [In memory index, Cloud Run pinned to one instance](docs/adr/0003-in-memory-index-single-instance.md)

## Run locally

```bash
cd backend
pip install -r requirements.txt -r requirements-dev.txt
uvicorn main:app --reload --port 8000
```

Put `GOOGLE_API_KEY=your_key` in a `.env` file at the repository root (it is gitignored; never commit it). Then open http://localhost:8000. To try the UI without a key, start with `REPOSAGE_FAKE=1`: answers are canned, but retrieval, citations and the Trace are real.

Useful settings (all optional, see `.env.example`):

- `GEMINI_MODEL`: the Gemini model for the agents and simple mode.
- `EMBEDDING_PROVIDER=local`: embed on your machine with sentence-transformers (`pip install -r requirements-local.txt`) instead of the Gemini embedding API, which has a small free-tier limit.
- `LLM_PROVIDER=groq` with `GROQ_API_KEY` (and `pip install -r requirements-groq.txt`): use Groq instead of Gemini.
- `GEMINI_API_KEYS=key1,key2`: switch to the next key on a quota error. Quota is per Google project, so the keys must come from different projects.

Tests run offline (no network, no key):

```bash
cd backend
python -m pytest -q
```

## Deploy

**Google Cloud Run with Vertex AI (what the live demo uses).** No API key: the Cloud Run service account calls Gemini on Vertex AI, and usage is billed to your Google Cloud billing account.

```bash
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com aiplatform.googleapis.com
# the default compute service account needs two roles (newer projects have none)
SA="serviceAccount:$(gcloud projects describe YOUR_PROJECT_ID --format='value(projectNumber)')-compute@developer.gserviceaccount.com"
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID --member="$SA" --role=roles/aiplatform.user
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID --member="$SA" --role=roles/run.builder
./deploy.sh
```

`deploy.sh` deploys to `asia-south1` with one instance, 2 GiB of memory and a 300 second request timeout, and uses `gemini-3.5-flash-lite` from the `global` Vertex location (override with `GEMINI_MODEL`). If you would rather use an AI Studio key, `export GOOGLE_API_KEY=...` before `./deploy.sh` (never put it in a file in this repository).

**Render (free, no credit card).** Push this repository to GitHub, then in Render choose New + > Blueprint and pick it. Render reads [`render.yaml`](render.yaml), builds the Dockerfile and asks for `GOOGLE_API_KEY`, which you enter in its dashboard. The free instance sleeps after about 15 idle minutes, and the in-memory index is lost when it sleeps, so index again after a wake-up.

## Limits

- 60 questions and 10 index runs per IP per hour, and 300 questions per day across all visitors (`REPOSAGE_DAILY_ASK_LIMIT`), because the public demo's model calls are billed.
- 500 indexable files per Repository, files up to 100 KB, secret shaped files never indexed.
- Only `https://github.com/owner/name` URLs; clone depth 1.

## Evaluation

[`eval/`](eval/README.md) holds a 10 question eval set about this repository and a runner. Latest run (`gemini-3.5-flash-lite`, free tier, local embeddings): **10 of 10** questions answered with the expected file cited, p50 latency 10.5 s, median 32,927 input and 368 output tokens per question. A pass means the expected file was cited with a line range that exists; it does not grade each claim. See [`eval/README.md`](eval/README.md) for the caveats.

## Known limitations

- The index is in memory: a restart drops it, and only one Repository is indexed at a time.
- A single instance, and a public endpoint without authentication. The container image is about 135 MB compressed.
- Only Python gets AST chunking; other languages use line windows.
- ADK marks `SequentialAgent` and `LoopAgent` as deprecated in favour of `Workflow`; see [`docs/plans/BACKLOG.md`](docs/plans/BACKLOG.md).
- Free-tier model quotas are small (roughly 15 requests per minute and a daily cap per model), and one agent question uses 5 to 20 model calls, so heavy use needs a paid key.
