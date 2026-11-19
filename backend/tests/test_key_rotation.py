import os

import keys
import main


def setup_function(_):
    keys.reset()


def test_keys_parsed_and_deduplicated(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEYS", "a, b ,c")
    monkeypatch.setenv("GEMINI_API_KEY", "b")
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    assert keys.all_keys() == ["a", "b", "c"]


def test_rotate_skips_exhausted_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEYS", "a,b")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    assert keys.activate() and os.environ["GOOGLE_API_KEY"] == "a"
    assert keys.rotate_after_quota_error() and os.environ["GOOGLE_API_KEY"] == "b"
    assert not keys.rotate_after_quota_error()  # both cooling down


def test_quota_error_detection():
    assert keys.is_quota_error(Exception("429 RESOURCE_EXHAUSTED. quota"))
    assert not keys.is_quota_error(Exception("503 UNAVAILABLE"))


def test_request_retries_with_next_key(monkeypatch):
    import asyncio

    monkeypatch.setenv("GEMINI_API_KEYS", "a,b")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    keys.activate()
    used = []

    async def work():
        used.append(os.environ["GOOGLE_API_KEY"])
        if len(used) == 1:
            raise Exception("429 RESOURCE_EXHAUSTED daily quota")
        return "done"

    assert asyncio.run(main._with_key_rotation(work)) == "done"
    assert used == ["a", "b"]


def test_gives_up_when_all_keys_used(monkeypatch):
    import asyncio

    monkeypatch.setenv("GEMINI_API_KEYS", "a")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    keys.activate()

    async def work():
        raise Exception("429 RESOURCE_EXHAUSTED")

    resp = asyncio.run(main._with_key_rotation(work))
    assert resp.status_code == 502
