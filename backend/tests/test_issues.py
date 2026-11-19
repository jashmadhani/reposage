import asyncio

import httpx
import pytest

import issues
import vector_store
from agent import pipeline
from embeddings import set_embedder
from tests.fakes import FakeEmbedder, FakeLlm


def test_parse_valid():
    assert issues.parse_issue_url("https://github.com/pallets/flask/issues/5432") == (
        "pallets", "flask", 5432,
    )
    assert issues.parse_issue_url("https://github.com/a/b.c/issues/1/")[1] == "b.c"


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/pallets/flask/pull/5432",
        "https://gitlab.com/pallets/flask/issues/1",
        "http://github.com/pallets/flask/issues/1",
        "https://github.com/pallets/flask/issues/abc",
        "https://github.com.evil.com/a/b/issues/1",
        "",
    ],
)
def test_parse_rejects(url):
    with pytest.raises(issues.IssueError):
        issues.parse_issue_url(url)


def _resp(status, payload):
    return httpx.Response(status, json=payload, request=httpx.Request("GET", "https://x"))


def test_fetch_truncates_body(monkeypatch):
    monkeypatch.setattr(
        httpx, "get", lambda *a, **k: _resp(200, {"title": "T", "body": "x" * 9000})
    )
    out = issues.fetch_issue("https://github.com/o/n/issues/1")
    assert out["title"] == "T" and len(out["body"]) == 4000


def test_fetch_pull_request_payload_rejected(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _resp(200, {"title": "T", "pull_request": {}}))
    with pytest.raises(issues.IssueError):
        issues.fetch_issue("https://github.com/o/n/issues/1")


def test_fetch_upstream_failure(monkeypatch):
    monkeypatch.setattr(httpx, "get", lambda *a, **k: _resp(404, {}))
    with pytest.raises(issues.IssueError) as e:
        issues.fetch_issue("https://github.com/o/n/issues/1")
    assert e.value.upstream


def test_issue_mode_pipeline_uses_fix_plan_instructions():
    set_embedder(FakeEmbedder())
    vector_store.build("demo", [("app/auth.py", "def login_user(name):\n    return name\n")])
    plan = "Files to change\n- app/auth.py:1-2\nSteps\nTests to update\nRisks"
    llm = FakeLlm(
        script={
            "researcher": ["Evidence: app/auth.py:1-2"],
            "writer": [plan],
            "reviewer": [{"call": "exit_loop"}],
        },
        calls={},
        requests=[],
    )
    issue = {"title": "Login {breaks}", "body": "name is None", "url": "u"}
    out = asyncio.run(pipeline.run("", issue=issue, llm=llm))
    assert out["answer"] == plan
    role, req = next(r for r in llm.requests if r[0] == "writer")
    assert "Fix Plan" in str(req.config.system_instruction)
    assert "Login {breaks}" in str(req.contents)
