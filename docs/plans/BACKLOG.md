# Backlog

Items outside the v2 plan. Not scheduled.

- **ADK deprecation:** google-adk 2.14 marks `SequentialAgent` and `LoopAgent` as deprecated in favour of `Workflow` (which cannot yet be used as an LlmAgent sub-agent). The plan and ADR 0001 specify the current classes, so v2 keeps them; revisit when `Workflow` is ready.
- **Python version:** development here ran on Python 3.13; the Dockerfile targets 3.12. Run the suite on 3.12 in CI before the first deploy.
- **Cloud Run deploy:** not done (needs a billing enabled Google Cloud project, run `./deploy.sh` from Cloud Shell). The image itself builds and boots locally: about 135 MB compressed, 640 MB unpacked.
- **Eval depth:** the eval passes 10 of 10 but only checks that the expected file is cited. Add a claim level check and an unseen repository set, and run it on a stronger model.
- **Fix Plan test citations:** the Tests to update item sometimes cites source files instead of test files; the Researcher may not be surfacing tests.
