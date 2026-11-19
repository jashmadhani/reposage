"""Offline fakes: tests never touch the network."""

import hashlib
import re

import numpy as np


class FakeEmbedder:
    """Deterministic 64 dim bag of words vectors from hashed tokens (signed
    hashing so unrelated texts land near zero cosine), L2 normalised."""

    DIM = 64

    def _vec(self, text):
        v = np.zeros(self.DIM, dtype="float32")
        for tok in re.findall(r"\w+", text.lower()):
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            v[h % self.DIM] += 1.0 if (h >> 8) & 1 else -1.0
        n = np.linalg.norm(v)
        return v / n if n else v

    def embed_documents(self, texts):
        return np.stack([self._vec(t) for t in texts]).astype("float32")

    def embed_query(self, text):
        return self._vec(text)[None, :]
