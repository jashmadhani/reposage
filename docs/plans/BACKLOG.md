# Backlog

Items outside the v2 plan. Not scheduled.

- **ADK deprecation:** google-adk 2.14 marks `SequentialAgent` and `LoopAgent` as deprecated in favour of `Workflow` (which cannot yet be used as an LlmAgent sub-agent). The plan and ADR 0001 specify the current classes, so v2 keeps them; revisit when `Workflow` is ready.
- **Python version:** development here ran on Python 3.13; the Dockerfile targets 3.12. Run the suite on 3.12 in CI before the first deploy.
- **Deploy follow ups:** the demo is live on Cloud Run with Vertex AI. Still open: a Cloud Armor or API gateway layer in front of the public endpoint, a custom domain, and an uptime check.
- **Eval depth:** the eval passes 10 of 10 but only checks that the expected file is cited. Add a claim level check and an unseen repository set, and run it on a stronger model.
- **Fix Plan test citations:** the Tests to update item sometimes cites source files instead of test files; the Researcher may not be surfacing tests.
- **Vertex model stability:** `gemini-3.5-flash` once hung for about 11 minutes on a single Vertex request, while `gemini-3.5-flash-lite` and `gemini-3.8-flash` were steady. The default is `gemini-3.5-flash-lite`; add a per request timeout on model calls.
