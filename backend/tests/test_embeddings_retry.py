import embeddings


class RateLimited(Exception):
    code = 429

    def __str__(self):
        return "429 RESOURCE_EXHAUSTED. Please retry in 2.5s."


class _Resp:
    class _E:
        values = [3.0, 4.0]

    embeddings = [_E()]


class _Models:
    def __init__(self):
        self.calls = 0

    def embed_content(self, **kw):
        self.calls += 1
        if self.calls < 3:
            raise RateLimited()
        return _Resp()


def make():
    e = embeddings.GeminiEmbedder.__new__(embeddings.GeminiEmbedder)
    e._client = type("C", (), {"models": _Models()})()
    e._sent = embeddings.deque()
    return e


def test_retries_on_429_then_succeeds(monkeypatch):
    slept = []
    monkeypatch.setattr(embeddings.time, "sleep", slept.append)
    e = make()
    vec = e.embed_query("hello")
    assert e._client.models.calls == 3
    assert slept == [3.5, 3.5]  # suggested 2.5s plus 1s margin
    assert abs(float(vec[0][0]) - 0.6) < 1e-6


def test_other_errors_are_not_retried(monkeypatch):
    monkeypatch.setattr(embeddings.time, "sleep", lambda s: None)
    e = make()
    e._client.models.embed_content = lambda **kw: (_ for _ in ()).throw(ValueError("bad"))
    try:
        e.embed_query("x")
        assert False
    except ValueError:
        pass


def test_pacing_waits_when_minute_budget_is_used(monkeypatch):
    clock = {"t": 1000.0}
    sleeps = []

    def fake_sleep(s):
        sleeps.append(s)
        clock["t"] += s

    monkeypatch.setattr(embeddings.time, "time", lambda: clock["t"])
    monkeypatch.setattr(embeddings.time, "sleep", fake_sleep)
    e = make()
    e._client.models.calls = 99  # never rate limited here
    e._sent = embeddings.deque()
    e._pace(60)
    e._pace(30)          # 90 used: still inside the budget, no wait
    assert sleeps == []
    e._pace(25)          # would be 115: must wait for the first batch to age out
    assert sleeps and clock["t"] >= 1060.0
