# RepoSage eval set

`reposage.evalset.json` holds 10 questions about RepoSage's own code in ADK eval set format. Each case's reference answer names the file a good answer must cite, for example `(backend/chunker.py)`.

Success target (PRD): 8 of 10 answered with the expected file cited.

## Run

This needs a real `GOOGLE_API_KEY`; it calls Gemini. Index RepoSage first, so the retrieval tools have something to search, then run the ADK evaluator against the agent module:

```bash
export GOOGLE_API_KEY=...   # in your shell only, never in a file
cd backend
adk eval <path-to-agent-module> ../eval/reposage.evalset.json
```

## Status

- The eval set file is validated against ADK's `EvalSet` model (10 valid cases).
- It has not been run. `adk eval` needs an agent module exposing `root_agent` with the repository already indexed; that wrapper is not part of the v2 plan and is listed in `docs/plans/BACKLOG.md`.
