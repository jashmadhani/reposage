"""Simple mode: one retrieval over Chunks plus one LLM call."""

import time

import vector_store

MODEL = "gemini-2.5-flash"
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


def generate(prompt: str) -> tuple[str, dict]:
    """The only place simple mode talks to the LLM. Returns (text, usage)."""
    from google import genai

    resp = genai.Client().models.generate_content(model=MODEL, contents=prompt)
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
