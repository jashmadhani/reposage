"""In-memory FAISS index over chunks, plus the raw files for exact reads.

The index lives in process memory, one repository at a time. That is why the
Cloud Run deploy pins max instances to 1: a second instance would not see the
index the first one built.
"""

import faiss

from chunker import Chunk, chunk_files
from embeddings import get_embedder

# Cosine similarity below this is treated as "not relevant". Without a floor,
# an off-topic question would still pull the top k chunks into the prompt.
MIN_SCORE = float(0.30)


class RepoIndex:
    def __init__(self, repo_name: str, files: list[tuple[str, str]]):
        self.repo_name = repo_name
        self.files = dict(files)
        self.chunks: list[Chunk] = chunk_files(files)
        if not self.chunks:
            raise ValueError("No chunkable content found.")

        vectors = get_embedder().embed_documents(
            [c.embedding_text() for c in self.chunks]
        )
        # Vectors are normalised, so inner product is cosine similarity.
        self.index = faiss.IndexFlatIP(vectors.shape[1])
        self.index.add(vectors)

    def search(self, query: str, k: int = 6, min_score: float = MIN_SCORE):
        """Return [(chunk, score)] best first, dropping low-similarity hits."""
        q = get_embedder().embed_query(query)
        k = min(k, len(self.chunks))
        scores, ids = self.index.search(q, k)
        return [
            (self.chunks[i], float(s))
            for s, i in zip(scores[0], ids[0])
            if i != -1 and s >= min_score
        ]

    def read_lines(self, path: str, start: int, end: int) -> str | None:
        text = self.files.get(path)
        if text is None:
            return None
        lines = text.splitlines()
        start = max(1, start)
        end = min(len(lines), end)
        return "\n".join(f"{n}: {lines[n - 1]}" for n in range(start, end + 1))


_current: RepoIndex | None = None


def build(repo_name, files) -> RepoIndex:
    global _current
    _current = RepoIndex(repo_name, files)
    return _current


def current() -> RepoIndex | None:
    return _current
