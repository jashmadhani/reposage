"""Embedding providers.

Two interchangeable backends, picked with the EMBEDDING_PROVIDER env var:

* "gemini" (default): Gemini's embedding API. No model weights in the
  container, so the Cloud Run image stays small and cold starts are fast.
* "local": sentence-transformers all-MiniLM-L6-v2 on CPU. No API calls for
  embeddings, but it pulls in PyTorch (install requirements-local.txt).

Both return L2-normalised float32 vectors, so inner product == cosine
similarity in the vector store.
"""

import os

import numpy as np

GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
GEMINI_EMBEDDING_DIM = 768
GEMINI_BATCH_SIZE = 100  # API limit on texts per request
LOCAL_EMBEDDING_MODEL = "all-MiniLM-L6-v2"


def _normalise(vectors) -> np.ndarray:
    arr = np.asarray(vectors, dtype="float32")
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return arr / norms


class GeminiEmbedder:
    def __init__(self):
        from google import genai

        self._client = genai.Client()  # reads GOOGLE_API_KEY / GEMINI_API_KEY

    def _embed(self, texts, task_type):
        from google.genai import types

        out = []
        for i in range(0, len(texts), GEMINI_BATCH_SIZE):
            batch = texts[i : i + GEMINI_BATCH_SIZE]
            resp = self._client.models.embed_content(
                model=GEMINI_EMBEDDING_MODEL,
                contents=batch,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=GEMINI_EMBEDDING_DIM,
                ),
            )
            out.extend(e.values for e in resp.embeddings)
        return _normalise(out)

    def embed_documents(self, texts):
        return self._embed(texts, "RETRIEVAL_DOCUMENT")

    def embed_query(self, text):
        return self._embed([text], "RETRIEVAL_QUERY")


class LocalEmbedder:
    def __init__(self):
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(LOCAL_EMBEDDING_MODEL)

    def embed_documents(self, texts):
        return _normalise(self._model.encode(texts, show_progress_bar=False))

    def embed_query(self, text):
        return _normalise(self._model.encode([text]))


_embedder = None


def get_embedder():
    """Create the configured embedder once and reuse it."""
    global _embedder
    if _embedder is None:
        provider = os.getenv("EMBEDDING_PROVIDER", "gemini").lower()
        _embedder = LocalEmbedder() if provider == "local" else GeminiEmbedder()
    return _embedder


def set_embedder(embedder):
    """Swap the embedder (used by tests)."""
    global _embedder
    _embedder = embedder
