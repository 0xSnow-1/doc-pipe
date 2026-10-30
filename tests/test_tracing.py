from src.tracing import configure_tracing, tracing_enabled


def test_env_unset() -> None:
    assert tracing_enabled({}) is False


def test_env_set_without_key() -> None:
    assert tracing_enabled({"LANGSMITH_TRACING": "true"}) is False


def test_env_set_with_key() -> None:
    assert tracing_enabled({"LANGSMITH_TRACING": "true", "LANGSMITH_API_KEY": "key"}) is True


def test_configure_tracing_off(monkeypatch) -> None:
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    assert configure_tracing() is False
    import os

    assert os.environ["LANGCHAIN_TRACING_V2"] == "false"


def test_configure_tracing_on(monkeypatch) -> None:
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "key")
    assert configure_tracing() is True
    import os

    assert os.environ["LANGCHAIN_TRACING_V2"] == "true"
    assert os.environ["LANGCHAIN_API_KEY"] == "key"
