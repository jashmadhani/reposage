# RepoSage eval set

`reposage.evalset.json` holds 10 questions about RepoSage's own code in ADK eval set format. Each case's reference answer names the file a good answer must cite, for example `(backend/chunker.py)`.

Success target (PRD): 8 of 10 answered with the expected file cited.

## Run

Needs a real key (`GOOGLE_API_KEY` or `GEMINI_API_KEY` in `.env`; it calls Gemini). From the repository root:

```bash
pip install -r backend/requirements.txt -r backend/requirements-local.txt
EMBEDDING_PROVIDER=local GEMINI_MODEL=gemini-3.5-flash-lite python eval/run_eval.py
```

`run_eval.py` indexes a clean snapshot of the committed files, asks each question through the real agent pipeline, and passes a case when the expected file is among the citations whose line range exists. It writes `results.json`. On the free tier it waits out per-minute rate limits, so a run takes several minutes.

## Result (2026-11-20)

| Model | Cases | Passed | p50 latency | Median tokens in / out |
| --- | --- | --- | --- | --- |
| gemini-3.5-flash-lite (free tier), local embeddings | 10 | **10** | 10.5 s | 32,927 / 368 |

Raw numbers: [`results.json`](results.json).

## What this does and does not show

- A pass means the expected file was cited with a line range that exists. It does not check that each claim is correct or that the range is the tightest one.
- The questions are about this repository and were written by its author, and the indexed snapshot includes the docs that describe the code, so this is easier than an unseen repository.
- One run, one model. Results will vary between runs.
- The ADK `adk eval` runner is not used; `run_eval.py` is a small custom runner over the same eval set file (which also validates against ADK's `EvalSet` model).
