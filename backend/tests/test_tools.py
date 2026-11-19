import pytest

import vector_store
from agent import tools
from embeddings import set_embedder
from tests.fakes import FakeEmbedder

BIG = "\n".join(f"line_{i} = {i}" for i in range(1, 301))
FILES = [
    ("app/auth.py", "def login_user(name, password):\n    token = make_token(name)\n    return token\n"),
    ("big.py", BIG),
    ("docs/notes.md", "gardening tips for tomatoes and basil in spring\n" * 3),
]


@pytest.fixture(autouse=True)
def index():
    set_embedder(FakeEmbedder())
    vector_store.build("demo", FILES)


def test_search_format():
    out = tools.search_code("login_user password token")
    assert out.startswith("### app/auth.py:1-3 (login_user) score=")
    assert "return token" in out


def test_search_no_results():
    assert tools.search_code("zzqx unrelated words") == "No relevant code found."


def test_read_unknown_path():
    assert tools.read_file_lines("nope.py", 1, 5).startswith("Error: unknown path")


def test_read_numbered_lines():
    assert tools.read_file_lines("app/auth.py", 1, 2) == (
        "1: def login_user(name, password):\n2:     token = make_token(name)"
    )


def test_read_caps_at_120_lines():
    out = tools.read_file_lines("big.py", 1, 300)
    assert len(out.splitlines()) == 120
    assert out.splitlines()[-1].startswith("120:")


def test_truncation(monkeypatch):
    monkeypatch.setattr(tools, "MAX_CHARS", 50)
    out = tools.read_file_lines("big.py", 1, 100)
    assert out.endswith("[truncated]") and len(out) < 80


def test_list_files_pattern():
    assert tools.list_files("*.py") == "app/auth.py\nbig.py"
    assert tools.list_files("*.zip") == "No files match."


def test_no_index(monkeypatch):
    monkeypatch.setattr(vector_store, "_current", None)
    assert tools.search_code("x") == tools.NOT_INDEXED
