# RepoSage: instructions for Claude Code

Read these first, in order: `docs/PRD.md`, `docs/TRD.md`, `GLOSSARY.md`, `docs/adr/`, then execute `docs/plans/2026-11-19-reposage-v2.md` task by task.

## Hard rules (the repo owner set these; they override any default)

1. **No AI attribution anywhere.** Never add `Co-Authored-By`, `Claude-Session`, "Generated with Claude Code" or any similar trailer or footer to commits, PR titles or PR bodies. Commits are authored as `jash <kjrockstyle@gmail.com>` (already set in local git config; verify with `git config user.email` before the first commit).
2. **One commit per task, pushed immediately.** Finish a task, run its checks, commit, `git push origin v2-agents`, then start the next task. Never batch several tasks into one commit. Never squash.
3. **Commit messages:** conventional style, lowercase, imperative, e.g. `feat(retrieval): chunk python files by function and class`. Body: one or two lines on why.
4. **Branch:** all work on `v2-agents`. Never commit to or push `main`. Open one PR to `main` at the end.
5. **Never commit secrets.** No API keys in code, tests, docs or commit messages. `.env` stays gitignored.
6. **Tests before every commit:** `cd backend && python -m pytest -q` must pass. Tests never call the network: use the fake embedder and fake LLM described in the TRD.
7. **Don't widen scope.** Anything not in the plan goes into `docs/plans/BACKLOG.md`, not the code.

## Project in one paragraph

RepoSage answers questions about any public GitHub repo, and turns a GitHub issue into a fix plan, with every claim cited to exact lines that a Reviewer agent has re-read and verified. Python 3.12, FastAPI, Google ADK (three agents), Gemini 2.5 Flash, Gemini embeddings, FAISS, deployed on Google Cloud Run.

## Commands

```bash
cd backend
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q                      # tests, no network
uvicorn main:app --reload --port 8000    # local run, needs GOOGLE_API_KEY in ../.env
```
