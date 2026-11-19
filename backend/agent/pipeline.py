"""Researcher, then a Writer/Reviewer loop, run with ADK and summarised as a
Trace.

ADK treats {name} in an instruction as session state and {name?} as optional
state. So the instruction texts below contain no other braces, and the user's
Question (which may contain braces) travels in the user message instead.
"""

import os
import time

from google.adk.agents import LlmAgent, LoopAgent, SequentialAgent
from google.adk.models import Gemini
from google.adk.runners import InMemoryRunner
from google.genai import types

from agent.tools import exit_loop, list_files, read_file_lines, search_code

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
APP_NAME = "reposage"
# Estimated price in USD per million tokens (gemini-2.5-flash). Shown as an estimate.
PRICE_IN_PER_M = 0.30
PRICE_OUT_PER_M = 2.50

RESEARCHER_INSTRUCTION = (
    "You are the Researcher. Gather Evidence from the indexed repository to "
    "answer the user's request. Call search_code with 2 to 4 different queries, "
    "then use read_file_lines to confirm the exact lines. Do NOT write the "
    "answer yourself. Finish with an evidence list only: one line per "
    "excerpt, written path:start-end - what it shows. Never invent paths or "
    "line numbers."
)

WRITER_INSTRUCTION = (
    "You are the Writer. Write the answer to the user's request using ONLY "
    "this Evidence:\n{evidence}\n\n"
    "Write the answer in your own words, not a copy of the Evidence. Every "
    "claim must end with a Citation written path:start-end that appears in "
    "the Evidence. An answer without Citations will be rejected. If the "
    "Evidence does not answer the request, say: Not found in this "
    "repository.\n"
    "Reviewer feedback to address, if any: {review?}"
)

REVIEWER_INSTRUCTION = (
    "You are the Reviewer. Here is the draft:\n{draft}\n\n"
    "For each Citation in the draft, call read_file_lines for that range and "
    "check that the claim is supported. If every claim holds, call exit_loop. "
    "Otherwise do not call exit_loop; list each unsupported claim and what is "
    "wrong with it."
)


ISSUE_RESEARCHER_INSTRUCTION = (
    "You are the Researcher. The user message is a GitHub Issue. Gather "
    "Evidence from the indexed repository about where and why the problem "
    "happens and which tests cover it. Call search_code with 2 to 4 different "
    "queries, then use read_file_lines to confirm the exact lines. Do NOT write "
    "the plan yourself. Finish with an evidence list only: one line per "
    "excerpt, written path:start-end - what it shows. Never invent paths or "
    "line numbers."
)

ISSUE_WRITER_INSTRUCTION = (
    "You are the Writer. Write a Fix Plan for the Issue in the user message "
    "using ONLY this Evidence:\n{evidence}\n\n"
    "Use exactly these sections: Files to change, Steps, Tests to update, "
    "Risks. Every item must end with a Citation written path:start-end that "
    "appears in the Evidence. If the Evidence is not enough to plan a fix, "
    "say: Not found in this repository.\n"
    "Reviewer feedback to address, if any: {review?}"
)


# Google's models return 503 during demand spikes and 429 on the free tier;
# both are usually gone within seconds, so retry with backoff.
RETRY = types.HttpRetryOptions(
    attempts=5, initial_delay=2, max_delay=20, http_status_codes=[503]  # 429 is handled by key rotation
)


GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")


def llm_provider() -> str:
    """LLM_PROVIDER wins; otherwise Groq if a Groq key is set, else Gemini."""
    explicit = os.getenv("LLM_PROVIDER")
    if explicit:
        return explicit.lower()
    return "groq" if os.getenv("GROQ_API_KEY") else "gemini"


def default_model():
    if llm_provider() == "groq":
        from google.adk.models.lite_llm import LiteLlm

        # Reads GROQ_API_KEY. The free tier caps tokens per minute, so let
        # litellm wait and retry on rate limits.
        return LiteLlm(model=f"groq/{GROQ_MODEL}", num_retries=8)
    return Gemini(model=MODEL, retry_options=RETRY)


def build_root(llm=None, issue_mode: bool = False) -> SequentialAgent:
    model = llm if llm is not None else default_model()
    researcher = LlmAgent(
        name="researcher",
        model=model,
        instruction=ISSUE_RESEARCHER_INSTRUCTION if issue_mode else RESEARCHER_INSTRUCTION,
        tools=[search_code, read_file_lines, list_files],
        output_key="evidence",
    )
    writer = LlmAgent(
        name="writer",
        model=model,
        instruction=ISSUE_WRITER_INSTRUCTION if issue_mode else WRITER_INSTRUCTION,
        output_key="draft",
    )
    reviewer = LlmAgent(
        name="reviewer",
        model=model,
        instruction=REVIEWER_INSTRUCTION,
        tools=[read_file_lines, exit_loop],
        output_key="review",
    )
    loop = LoopAgent(name="refine", sub_agents=[writer, reviewer], max_iterations=2)
    return SequentialAgent(name="reposage", sub_agents=[researcher, loop])


def _preview(value, limit=200) -> str:
    text = value if isinstance(value, str) else str(value)
    return text if len(text) <= limit else text[:limit] + "..."


async def run(question: str, issue: dict | None = None, llm=None) -> dict:
    """Run the pipeline once. Returns {answer, trace}."""
    root = build_root(llm, issue_mode=issue is not None)
    if issue is not None:
        question = f"Issue: {issue['title']}\n\n{issue['body']}"
    runner = InMemoryRunner(agent=root, app_name=APP_NAME)
    session = await runner.session_service.create_session(
        app_name=APP_NAME, user_id="web"
    )
    message = types.Content(role="user", parts=[types.Part(text=question)])

    steps, tokens_in, tokens_out, llm_calls, tool_calls = [], 0, 0, 0, 0
    started = time.time()
    async for event in runner.run_async(
        user_id="web", session_id=session.id, new_message=message
    ):
        if event.usage_metadata is not None:
            llm_calls += 1
            tokens_in += event.usage_metadata.prompt_token_count or 0
            tokens_out += event.usage_metadata.candidates_token_count or 0
        for call in event.get_function_calls():
            tool_calls += 1
            steps.append(
                {
                    "agent": event.author,
                    "kind": "tool",
                    "name": call.name,
                    "args": dict(call.args or {}),
                    "preview": "",
                }
            )
        for resp in event.get_function_responses():
            for step in reversed(steps):
                if step["kind"] == "tool" and step["name"] == resp.name and not step["preview"]:
                    step["preview"] = _preview((resp.response or {}).get("result", resp.response))
                    break
        if event.content and event.content.parts and not event.get_function_calls():
            text = "".join(p.text or "" for p in event.content.parts)
            if text and event.author != "user":
                steps.append(
                    {"agent": event.author, "kind": "llm", "name": event.author,
                     "args": {}, "preview": _preview(text)}
                )

    final = await runner.session_service.get_session(
        app_name=APP_NAME, user_id="web", session_id=session.id
    )
    trace = {
        "steps": steps,
        "llm_calls": llm_calls,
        "tool_calls": tool_calls,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "latency_ms": int((time.time() - started) * 1000),
        "est_cost_usd": 0.0
        if (llm is None and llm_provider() == "groq")
        else round(
            tokens_in / 1e6 * PRICE_IN_PER_M + tokens_out / 1e6 * PRICE_OUT_PER_M, 6
        ),
    }
    return {"answer": final.state.get("draft", ""), "trace": trace}
