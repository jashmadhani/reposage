from agent import pipeline


def test_groq_chosen_when_key_present(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "x")
    assert pipeline.llm_provider() == "groq"


def test_gemini_by_default(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert pipeline.llm_provider() == "gemini"


def test_explicit_provider_wins(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "x")
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    assert pipeline.llm_provider() == "gemini"
