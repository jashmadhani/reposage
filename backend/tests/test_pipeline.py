import asyncio
import re

import pytest

import vector_store
from agent import pipeline
from embeddings import set_embedder
from tests.fakes import FakeEmbedder, FakeLlm

FILES = [
    ("app/auth.py", "def login_user(name, password):\n    token = make_token(name)\n    return token\n"),
]
SEARCH = {"call": "search_code", "args": {"query": "login_user"}}
READ = {"call": "read_file_lines", "args": {"path": "app/auth.py", "start": 1, "end": 3}}
APPROVE = {"call": "exit_loop"}


@pytest.fixture(autouse=True)
def index():
    set_embedder(FakeEmbedder())
    vector_store.build("demo", FILES)


def make_llm(**script):
    return FakeLlm(script=script, calls={}, requests=[])


def test_approved_first_pass_runs_writer_once():
    llm = make_llm(
        researcher=[SEARCH, "Evidence: app/auth.py:1-3 makes a token"],
        writer=["Login makes a token. app/auth.py:1-3"],
        reviewer=[READ, APPROVE],
    )
    out = asyncio.run(pipeline.run("how does login work?", llm=llm))
    assert llm.calls["writer"] == 1
    assert llm.calls["reviewer"] == 2
    assert out["answer"] == "Login makes a token. app/auth.py:1-3"


def test_rejected_then_approved_runs_writer_twice():
    llm = make_llm(
        researcher=[SEARCH, "Evidence: app/auth.py:1-3"],
        writer=["Bad claim. app/auth.py:1-3", "Fixed claim. app/auth.py:1-3"],
        reviewer=["Unsupported: bad claim", READ, APPROVE],
    )
    out = asyncio.run(pipeline.run("how does login work?", llm=llm))
    assert llm.calls["writer"] == 2
    assert out["answer"] == "Fixed claim. app/auth.py:1-3"
    writer2 = [r for role, r in llm.requests if role == "writer"][1]
    assert "Unsupported: bad claim" in str(writer2.config.system_instruction)


def test_loop_stops_after_two_iterations_without_approval():
    llm = make_llm(
        researcher=["Evidence: none"],
        writer=["one", "two"],
        reviewer=["no", "still no"],
    )
    out = asyncio.run(pipeline.run("q", llm=llm))
    assert llm.calls["writer"] == 2 and out["answer"] == "two"


def test_trace_counts_tools_and_sums_tokens():
    llm = make_llm(
        researcher=[SEARCH, "Evidence: app/auth.py:1-3"],
        writer=["Login makes a token. app/auth.py:1-3"],
        reviewer=[READ, APPROVE],
    )
    trace = asyncio.run(pipeline.run("q", llm=llm))["trace"]
    assert trace["tool_calls"] == 3  # search_code, read_file_lines, exit_loop
    assert trace["llm_calls"] == 5   # researcher 2, writer 1, reviewer 2
    assert trace["tokens_in"] == 50 and trace["tokens_out"] == 25
    assert trace["est_cost_usd"] > 0
    names = [s["name"] for s in trace["steps"] if s["kind"] == "tool"]
    assert names == ["search_code", "read_file_lines", "exit_loop"]


def test_instructions_only_contain_state_braces():
    for text in (
        pipeline.RESEARCHER_INSTRUCTION,
        pipeline.WRITER_INSTRUCTION,
        pipeline.REVIEWER_INSTRUCTION,
    ):
        assert set(re.findall(r"\{[^}]*\}", text)) <= {"{evidence}", "{review?}", "{draft}"}


def test_question_with_braces_does_not_break_rendering():
    llm = make_llm(
        researcher=["Evidence: x"],
        writer=["ok app/auth.py:1-3"],
        reviewer=[APPROVE],
    )
    out = asyncio.run(pipeline.run("what does {this} dict {} do?", llm=llm))
    assert out["answer"] == "ok app/auth.py:1-3"
