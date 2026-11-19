# Backlog

Items outside the v2 plan. Not scheduled.

- **ADK deprecation:** google-adk 2.14 marks `SequentialAgent` and `LoopAgent` as deprecated in favour of `Workflow` (which cannot yet be used as an LlmAgent sub-agent). The plan and ADR 0001 specify the current classes, so v2 keeps them; revisit when `Workflow` is ready.
- **Python version:** development here ran on Python 3.13; the Dockerfile targets 3.12. Run the suite on 3.12 in CI before the first deploy.
- **Image build not verified locally:** the Docker daemon was not running during Task 7, so `docker build .` has not been run. Build it once (or let `gcloud run deploy --source .` do it) and confirm the image is under 500 MB.
