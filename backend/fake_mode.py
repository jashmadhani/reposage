"""REPOSAGE_FAKE=1: run the whole app offline so the UI can be demoed without
an API key. Answers are canned; retrieval, citations and Trace are real."""

import vector_store
from embeddings import set_embedder


def enable():
    import rag_pipeline
    from tests.fakes import FakeEmbedder

    set_embedder(FakeEmbedder())
    rag_pipeline.generate = generate


def generate(prompt: str):
    return "Demo answer (fake mode, no model was called).", {"tokens_in": 0, "tokens_out": 0}


def llm_for(index):
    """A scripted FakeLlm that cites the first lines of the first indexed file."""
    from tests.fakes import FakeLlm

    path = next(iter(index.files))
    end = min(3, len(index.files[path].splitlines()))
    cite = f"{path}:1-{end}"
    return FakeLlm(
        script={
            "researcher": [
                {"call": "search_code", "args": {"query": path}},
                f"Evidence: {cite}",
            ],
            "writer": [f"Demo answer (fake mode, no model was called). {cite}"],
            "reviewer": [
                {"call": "read_file_lines", "args": {"path": path, "start": 1, "end": end}},
                {"call": "exit_loop"},
            ],
        },
        calls={},
        requests=[],
    )
