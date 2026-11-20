import pytest
from fastapi.testclient import TestClient

import fake_mode
import issues
import limits
import main
import rag_pipeline
import repo_loader
import vector_store
from embeddings import set_embedder
from tests.fakes import FakeEmbedder

URL = "https://github.com/acme/demo"


@pytest.fixture
def client(tmp_path, monkeypatch):
    (tmp_path / "auth.py").write_text(
        "def login_user(name, password):\n    token = make_token(name)\n    return token\n"
    )
    (tmp_path / "README.md").write_text("# demo\nA tiny demo repository for tests.\n")
    set_embedder(FakeEmbedder())
    limits.reset()
    main._repo.clear()
    monkeypatch.setattr(vector_store, "_current", None)
    monkeypatch.setattr(repo_loader, "clone_repo", lambda url: (str(tmp_path), "demo"))
    monkeypatch.setattr(main, "FAKE", True)
    monkeypatch.setattr(rag_pipeline, "generate", fake_mode.generate)
    return TestClient(main.app)


def index(client):
    return client.post("/index", json={"repo_url": URL})


def test_health_before_and_after_index(client):
    assert client.get("/health").json() == {"ok": True, "repo": None}
    assert index(client).json()["status"] == "ok"
    assert client.get("/health").json() == {"ok": True, "repo": "demo"}


def test_index_reports_counts(client):
    body = index(client).json()
    assert body["files_indexed"] == 2 and body["chunks_indexed"] >= 2
    assert body["repo_name"] == "demo" and "seconds" in body


@pytest.mark.parametrize("bad", ["http://github.com/a/b", "https://evil.com/a/b", "", "https://github.com/a"])
def test_index_rejects_bad_urls(client, bad):
    r = client.post("/index", json={"repo_url": bad})
    assert r.status_code == 400 and r.json()["status"] == "error"


def test_index_rejects_too_many_files(client, monkeypatch):
    monkeypatch.setattr(repo_loader, "MAX_FILES", 1)
    assert index(client).status_code == 400


def test_ask_before_index_is_409(client):
    assert client.post("/ask", json={"question": "x"}).status_code == 409


def test_ask_agent_mode_with_fakes(client):
    index(client)
    r = client.post("/ask", json={"question": "how does login work?", "mode": "agent"})
    assert r.status_code == 200
    body = r.json()
    assert "Demo answer" in body["answer"]
    cite = body["citations"][0]
    assert cite["verified"] is True
    assert cite["url"].startswith("https://github.com/acme/demo/blob/HEAD/")
    assert body["trace"]["tool_calls"] >= 2


def test_ask_simple_mode_with_fakes(client):
    index(client)
    r = client.post("/ask", json={"question": "login_user password token", "mode": "simple"})
    assert r.status_code == 200 and "Demo answer" in r.json()["answer"]


def test_ask_validation(client):
    index(client)
    assert client.post("/ask", json={"question": "  "}).status_code == 400
    assert client.post("/ask", json={"question": "x", "mode": "bogus"}).status_code == 400


def test_issue_from_other_repo_is_409(client):
    index(client)
    r = client.post("/issue", json={"issue_url": "https://github.com/other/thing/issues/3"})
    assert r.status_code == 409


def test_issue_bad_url_is_400(client):
    index(client)
    assert client.post("/issue", json={"issue_url": "https://github.com/acme/demo/pull/3"}).status_code == 400


def test_issue_happy_path(client, monkeypatch):
    index(client)
    monkeypatch.setattr(
        issues, "fetch_issue", lambda url: {"title": "Login fails", "body": "None name", "url": url}
    )
    r = client.post("/issue", json={"issue_url": "https://github.com/acme/demo/issues/3"})
    assert r.status_code == 200 and r.json()["citations"]


def test_issue_github_failure_is_502(client, monkeypatch):
    index(client)

    def boom(url):
        raise issues.IssueError("GitHub returned 404", upstream=True)

    monkeypatch.setattr(issues, "fetch_issue", boom)
    r = client.post("/issue", json={"issue_url": "https://github.com/acme/demo/issues/3"})
    assert r.status_code == 502


def test_61st_ask_is_429(client):
    index(client)
    codes = [
        client.post("/ask", json={"question": "login", "mode": "simple"}).status_code
        for _ in range(61)
    ]
    assert codes[:60] == [200] * 60 and codes[60] == 429


def test_index_limit_and_forwarded_for(client):
    codes = [index(client).status_code for _ in range(11)]
    assert codes[-1] == 429
    other = client.post(
        "/index", json={"repo_url": URL}, headers={"X-Forwarded-For": "9.9.9.9, 10.0.0.1"}
    )
    assert other.status_code == 200


def test_limiter_window_expires():
    limits.reset()
    assert limits.check("ip", "ask", 1, now=0)
    assert not limits.check("ip", "ask", 1, now=10)
    assert limits.check("ip", "ask", 1, now=3601)


def test_global_daily_cap_applies_across_visitors(client, monkeypatch):
    index(client)
    monkeypatch.setattr(main, "DAILY_ASK_LIMIT", 2)
    def ask(ip):
        return client.post(
            "/ask", json={"question": "login", "mode": "simple"}, headers={"X-Forwarded-For": ip}
        ).status_code
    assert [ask("1.1.1.1"), ask("2.2.2.2"), ask("3.3.3.3")] == [200, 200, 429]
