import citations
import rag_pipeline
import vector_store
from embeddings import set_embedder
from tests.fakes import FakeEmbedder

FILES = [
    (
        "app/auth.py",
        "def login_user(name, password):\n    token = make_token(name)\n    return token\n",
    ),
    ("docs/notes.md", "gardening tips for tomatoes and basil in spring\n" * 3),
]


def test_parse_citations_unique_in_order():
    text = "A a.py:1-5. B b/c.py:10-24 and again a.py:1-5."
    assert citations.parse_citations(text) == [("a.py", 1, 5), ("b/c.py", 10, 24)]


def test_github_url_line_anchor():
    url = citations.github_url("https://github.com/o/n.git", "src/x.py", 10, 24)
    assert url == "https://github.com/o/n/blob/HEAD/src/x.py#L10-L24"


def test_resolve_keeps_only_indexed_paths():
    set_embedder(FakeEmbedder())
    idx = vector_store.build("demo", FILES)
    out = citations.resolve(
        "ok app/auth.py:1-3 fake nope.py:1-2 bad app/auth.py:2-99",
        idx,
        "https://github.com/o/n",
    )
    assert [c["path"] for c in out] == ["app/auth.py", "app/auth.py"]
    assert out[0]["verified"] is True
    assert out[1]["verified"] is False


def test_simple_mode_uses_monkeypatched_generate(monkeypatch):
    set_embedder(FakeEmbedder())
    vector_store.build("demo", FILES)
    seen = {}

    def fake_generate(prompt):
        seen["prompt"] = prompt
        return "Login makes a token. app/auth.py:1-3", {"tokens_in": 7, "tokens_out": 3}

    monkeypatch.setattr(rag_pipeline, "generate", fake_generate)
    answer, cites, trace = rag_pipeline.answer_question("login_user password token")
    assert "app/auth.py:1-3" in answer
    assert cites == [("app/auth.py", 1, 3)]
    assert "app/auth.py:1-3" in seen["prompt"]
    assert trace["llm_calls"] == 1 and trace["tokens_in"] == 7


def test_simple_mode_off_topic_skips_llm(monkeypatch):
    set_embedder(FakeEmbedder())
    vector_store.build("demo", FILES)
    monkeypatch.setattr(
        rag_pipeline, "generate", lambda p: (_ for _ in ()).throw(AssertionError)
    )
    answer, cites, trace = rag_pipeline.answer_question("zzqx unrelated words")
    assert answer == rag_pipeline.NOT_FOUND and cites == []
    assert trace["llm_calls"] == 0
