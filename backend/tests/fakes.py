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


# --- FakeLlm: scripted ADK model, no network -------------------------------

from google.adk.models import BaseLlm, LlmResponse  # noqa: E402
from google.adk.models._capabilities import LlmCapabilities  # noqa: E402
from google.genai import types  # noqa: E402


def _role_of(llm_request) -> str:
    """Which agent is calling, read from the marker at the start of its
    instruction ("You are the Researcher." and so on)."""
    si = llm_request.config.system_instruction
    text = si if isinstance(si, str) else str(si)
    for role in ("researcher", "writer", "reviewer"):
        if f"You are the {role.capitalize()}" in text:
            return role
    raise AssertionError(f"FakeLlm: unknown agent in instruction: {text[:80]!r}")


class FakeLlm(BaseLlm):
    """Returns scripted responses per agent role.

    script = {"researcher": [...], "writer": [...], "reviewer": [...]}, each
    item either a string (a text reply) or {"call": name, "args": {...}} (a
    tool call). Items are consumed in order; asking for more raises.
    Every reply reports 10 prompt and 5 output tokens.
    """

    model: str = "fake"
    script: dict = {}
    calls: dict = {}
    requests: list = []

    @classmethod
    def supported_models(cls) -> list[str]:
        return ["fake"]

    @property
    def capabilities(self) -> LlmCapabilities:
        return LlmCapabilities(output_schema_and_tools=False)

    async def generate_content_async(self, llm_request, stream=False):
        role = _role_of(llm_request)
        self.requests.append((role, llm_request))
        n = self.calls.get(role, 0)
        self.calls[role] = n + 1
        items = self.script.get(role, [])
        if n >= len(items):
            raise AssertionError(f"FakeLlm: no scripted reply #{n + 1} for {role}")
        item = items[n]
        if isinstance(item, str):
            part = types.Part(text=item)
        else:
            part = types.Part(
                function_call=types.FunctionCall(name=item["call"], args=item.get("args", {}))
            )
        yield LlmResponse(
            content=types.Content(role="model", parts=[part]),
            usage_metadata=types.GenerateContentResponseUsageMetadata(
                prompt_token_count=10, candidates_token_count=5
            ),
        )
