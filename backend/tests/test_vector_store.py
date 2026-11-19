import pytest

import embeddings
import vector_store
from tests.fakes import FakeEmbedder

FILES = [
    ("auth.py", "def login_user(name, password):\n    return check_password_hash(name, password)\n"),
    ("db.py", "def connect_database(url):\n    return open_connection_pool(url)\n"),
    ("README.md", "This project renders invoices into pdf documents for customers.\n"),
]


@pytest.fixture(autouse=True)
def fake_embedder():
    embeddings.set_embedder(FakeEmbedder())
    yield
    embeddings.set_embedder(None)
    vector_store._current = None


def test_search_ranks_matching_chunk_first():
    idx = vector_store.build("demo", FILES)
    hits = idx.search("login_user password", min_score=-1.0)
    assert hits[0][0].path == "auth.py"
    assert hits[0][1] >= hits[1][1]


def test_min_score_floor_drops_irrelevant():
    idx = vector_store.build("demo", FILES)
    assert idx.search("zebra xylophone quartz") == []
    assert vector_store.current() is idx


def test_read_lines_clamps_and_numbers():
    idx = vector_store.build("demo", FILES)
    assert idx.read_lines("auth.py", 0, 99) == (
        "1: def login_user(name, password):\n"
        "2:     return check_password_hash(name, password)"
    )
    assert idx.read_lines("auth.py", 2, 2).startswith("2: ")
    assert idx.read_lines("nope.py", 1, 2) is None


def test_no_chunkable_content_raises():
    with pytest.raises(ValueError):
        vector_store.RepoIndex("x", [("a.py", "")])


def test_get_embedder_uses_set_embedder():
    fake = FakeEmbedder()
    embeddings.set_embedder(fake)
    assert embeddings.get_embedder() is fake
