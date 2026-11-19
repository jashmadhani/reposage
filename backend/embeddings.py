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
import re
import time
from collections import deque

import numpy as np

GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")
GEMINI_EMBEDDING_DIM = 768
GEMINI_BATCH_SIZE = 25  # texts per request (the API allows up to 100)
# Free tier: 100 embedding requests per minute, one per text, and rejected
# requests count too. Stay under that ourselves instead of retrying into it.
RATE_BUDGET_PER_MINUTE = 90
LOCAL_EMBEDDING_MODEL = "all-MiniLM-L6-v2"


def _normalise(vectors) -> np.ndarray:
    arr = np.asarray(vectors, dtype="float32")
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return arr / norms


MAX_RETRIES = 8


def _retry_delay(error) -> float | None:
    """Seconds to wait if `error` is a rate limit (HTTP 429), else None."""
    if getattr(error, "code", None) != 429:
        return None
    m = re.search(r"retry in ([\d.]+)s", str(error))
    return float(m.group(1)) + 1 if m else 15.0


class GeminiEmbedder:
    def __init__(self):
        from google import genai

        self._client = genai.Client()  # reads GOOGLE_API_KEY / GEMINI_API_KEY
        self._sent = deque()  # (timestamp, number of texts) for the last minute

    def _embed(self, texts, task_type):
        from google.genai import types

        out = []
        for i in range(0, len(texts), GEMINI_BATCH_SIZE):
            batch = texts[i : i + GEMINI_BATCH_SIZE]
            resp = self._embed_batch(batch, task_type, types)
            out.extend(e.values for e in resp.embeddings)
        return _normalise(out)

    def _pace(self, n):
        """Wait until sending n more texts keeps us within the per-minute budget."""
        while True:
            now = time.time()
            while self._sent and self._sent[0][0] <= now - 60:
                self._sent.popleft()
            used = sum(k for _, k in self._sent)
            if used + n <= RATE_BUDGET_PER_MINUTE:
                self._sent.append((now, n))
                return
            time.sleep(max(1.0, self._sent[0][0] + 60 - now))

    def _embed_batch(self, batch, task_type, types):
        """One API call. The free tier allows 100 embedding requests per
        minute, so on a 429 wait the suggested delay and retry."""
        for attempt in range(MAX_RETRIES + 1):
            self._pace(len(batch))
            try:
                return self._client.models.embed_content(
                    model=GEMINI_EMBEDDING_MODEL,
                    contents=batch,
                    config=types.EmbedContentConfig(
                        task_type=task_type,
                        output_dimensionality=GEMINI_EMBEDDING_DIM,
                    ),
                )
            except Exception as e:
                delay = _retry_delay(e)
                if delay is None or attempt == MAX_RETRIES:
                    raise
                time.sleep(delay)

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
