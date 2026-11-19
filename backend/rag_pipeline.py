"""Simple mode: one retrieval over Chunks plus one LLM call."""

import os
import time

import vector_store

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

_client = None
NOT_FOUND = "Not found in this repository."


def build_prompt(question: str, results) -> str:
    blocks = []
    for chunk, score in results:
        label = f"{chunk.citation}" + (f" ({chunk.symbol})" if chunk.symbol else "")
        blocks.append(f"### {label}\n{chunk.text}")
    evidence = "\n\n".join(blocks)
    return (
        "You are answering a question about a code repository.\n"
        "Use ONLY the excerpts below. After every claim, add a citation in the "
        "form path:start-end using the line ranges from the excerpt headings. "
        "If the excerpts do not answer the question, reply exactly: "
        f"{NOT_FOUND}\n\n"
        f"EXCERPTS:\n{evidence}\n\n"
        f"QUESTION: {question}\n\nANSWER:"
    )


def _generate_groq(prompt: str) -> tuple[str, dict]:
    import httpx

    resp = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"},
        json={
            "model": os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    usage = data.get("usage", {})
    return data["choices"][0]["message"]["content"] or "", {
        "tokens_in": usage.get("prompt_tokens", 0),
        "tokens_out": usage.get("completion_tokens", 0),
    }


def generate(prompt: str) -> tuple[str, dict]:
    """The only place simple mode talks to the LLM. Returns (text, usage)."""
    from agent.pipeline import llm_provider

    if llm_provider() == "groq":
        return _generate_groq(prompt)
    global _client
    from google import genai

    # Keep the client alive: a temporary one is closed when garbage collected,
    # which fails the request with "client has been closed".
    if _client is None:
        from google.genai import types

        _client = genai.Client(
            http_options=types.HttpOptions(
                retry_options=types.HttpRetryOptions(
                    attempts=5, initial_delay=2, max_delay=20, http_status_codes=[429, 503]
                )
            )
        )
    resp = _client.models.generate_content(model=MODEL, contents=prompt)
    meta = resp.usage_metadata
    usage = {
        "tokens_in": getattr(meta, "prompt_token_count", 0) or 0,
        "tokens_out": getattr(meta, "candidates_token_count", 0) or 0,
    }
    return resp.text or "", usage


def answer_question(question: str):
    """Returns (answer, citations, trace). `citations` are (path, start, end)
    tuples taken from the retrieved Chunks' ranges that the answer cites."""
    from citations import parse_citations

    index = vector_store.current()
    started = time.time()
    results = index.search(question)
    if not results:
        trace = _trace([], 0, {"tokens_in": 0, "tokens_out": 0}, started, 0)
        return NOT_FOUND, [], trace

    text, usage = generate(build_prompt(question, results))
    steps = [
        {
            "agent": "simple",
            "kind": "tool",
            "name": "search_code",
            "args": {"query": question},
            "preview": ", ".join(c.citation for c, _ in results),
        }
    ]
    trace = _trace(steps, 1, usage, started, 1)
    return text, parse_citations(text), trace


def _trace(steps, llm_calls, usage, started, tool_calls):
    return {
        "steps": steps,
        "llm_calls": llm_calls,
        "tool_calls": tool_calls,
        "tokens_in": usage["tokens_in"],
        "tokens_out": usage["tokens_out"],
        "latency_ms": int((time.time() - started) * 1000),
        "est_cost_usd": 0.0,
    }
