# RepoSage v2: Product Requirements

**Goal:** a public tool a developer or recruiter opens in one click, points at any public GitHub repository, and gets answers or issue fix plans where every claim cites exact lines that were verified.

## Problem

Onboarding to an unfamiliar codebase means grepping, guessing and asking teammates. Generic chatbots invent file paths. Existing tools (DeepWiki, Greptile, Copilot Chat) answer questions with citations, but none turns an issue into a concrete fix plan, and none shows that its citations were checked. RepoSage v1 also embedded whole files, so one relevant function inside a large file was drowned out.

## Users

| User | Need | How v2 serves it |
| --- | --- | --- |
| Developer new to a repository | Where does X happen, how does A call B | Answers with Verified Citations |
| Open source newcomer | Where do I start on this "good first issue" | Fix Plan from the issue URL |
| Recruiter or interviewer | See real AI engineering in two minutes | Live URL, Trace panel, README video |

## Goals

1. Every claim in an Answer or Fix Plan carries a Verified Citation.
2. Agent reasoning is visible: which agent ran, which tools, tokens, cost.
3. Publicly reachable on Google Cloud Run.
4. Simple enough that its author can defend every design choice.

## Non goals

User accounts, saved history, private repositories, monorepos above the size caps, fine tuning.

## Functional requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| F1 | Index a public `https://github.com/owner/name` URL; report files, chunks, seconds | Must |
| F2 | Chunk Python by top level function and class; other files by 60 line windows, 15 overlap | Must |
| F3 | `agent` mode: Answer with `path:start-end` Citations | Must |
| F4 | Reviewer re-reads every cited range; loops the Writer at most twice | Must |
| F5 | Trace: steps, tool calls, input and output tokens, latency, estimated cost | Must |
| F6 | `simple` mode: one retrieval plus one LLM call | Should |
| F7 | Off topic Question returns "not found in this repository" | Should |
| F8 | `/health` endpoint | Must |
| F9 | Frontend: Answer, Verified Citations, collapsible Trace | Must |
| F10 | Issue to Fix Plan: paste an issue URL from the indexed Repository; get files and lines to change, ordered steps, tests to update, risks | Must |
| F11 | Verified Citations link to exact lines on GitHub; unsupported claims are removed | Must |
| F12 | Limits: 60 questions and 10 index runs per IP per hour; 500 files per Repository | Must |
| F13 | README launch video | Should |
| F14 | ADK eval set of 10 questions with expected files, runnable with one command | Should |

## Non functional requirements

- Agent mode response under 30 s for about 200 files; indexing under 60 s.
- API key only in environment; never logged, committed or sent to the browser.
- Secret shaped files never indexed (kept from v1).
- Container image under 500 MB.

## Success metrics

- 8 of 10 eval questions answered with the expected file cited.
- Zero unverified claims in approved Answers on the eval set.
- p50 latency and tokens per request reported in the README.

## Decisions (from the grilling round)

- Submit the application after midnight even if the deploy slips; the resume claims only what is live.
- Demo: open URL, paste RepoSage's own repository, ask or paste an issue, see Verified Citations and the Trace.
- Three agents (ADR 0001). Cloud Run only, no Render fallback. Free tier Gemini key.
