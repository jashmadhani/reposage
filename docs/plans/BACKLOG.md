# Backlog

Items outside the v2 plan. Not scheduled.

- **ADK deprecation:** google-adk 2.14 marks `SequentialAgent` and `LoopAgent` as deprecated in favour of `Workflow` (which cannot yet be used as an LlmAgent sub-agent). The plan and ADR 0001 specify the current classes, so v2 keeps them; revisit when `Workflow` is ready.
- **Python version:** development here ran on Python 3.13; the Dockerfile targets 3.12. Run the suite on 3.12 in CI before the first deploy.
- **Deploy:** not done yet. Cloud Run needs a Google Cloud project with an open billing account (the current one is closed). Hugging Face Docker Spaces now require a paid plan. `render.yaml` targets Render's free Docker web service, which needs no card. The image runs as a non-root user: about 135 MB compressed, 640 MB unpacked, about 100 MB of memory in use.
- **Eval depth:** the eval passes 10 of 10 but only checks that the expected file is cited. Add a claim level check and an unseen repository set, and run it on a stronger model.
- **Fix Plan test citations:** the Tests to update item sometimes cites source files instead of test files; the Researcher may not be surfacing tests.
