# Three agent Google ADK pipeline, no Planner

Answers run through a Google ADK `SequentialAgent`: a Researcher with retrieval tools, then a `LoopAgent` (max 2 iterations) of Writer and Reviewer. We dropped a separate Planner because the Researcher already chooses its own search queries through tool calling, so a Planner added one LLM call per request without new behaviour. ADK was chosen over LangGraph or a hand written loop because it is Google's own framework and maps directly onto the target role.

## Considered Options

- Four agents with a Planner: rejected for latency and cost, can return later.
- Single call RAG (v1 behaviour): kept as `simple` mode for speed and as a fallback.
