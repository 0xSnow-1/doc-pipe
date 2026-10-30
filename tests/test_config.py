from pathlib import Path

import pytest

from src.config import ConfigError, build_config, load_environment


def test_dotenv_does_not_override_real_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("BEDROCK_MODEL_ID=from-file\nBEDROCK_REGION=from-file\n")
    monkeypatch.setenv("BEDROCK_MODEL_ID", "from-real-env")
    monkeypatch.delenv("BEDROCK_REGION", raising=False)
    load_environment(env_file)
    import os

    assert os.environ["BEDROCK_MODEL_ID"] == "from-real-env"
    assert os.environ["BEDROCK_REGION"] == "from-file"


def test_missing_model_id_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BEDROCK_MODEL_ID", raising=False)
    with pytest.raises(ConfigError, match="BEDROCK_MODEL_ID"):
        build_config("1.0.0", "2026-10-30")


def test_config_hash_is_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BEDROCK_MODEL_ID", "global.anthropic.claude-haiku-4-5-20251001-v1:0")
    monkeypatch.setenv("BEDROCK_REGION", "us-east-1")
    first = build_config("1.0.0", "2026-10-30")
    second = build_config("1.0.0", "2026-10-30")
    assert first.config_hash() == second.config_hash()


def test_config_hash_changes_with_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BEDROCK_MODEL_ID", "model-a")
    first = build_config("1.0.0", "2026-10-30")
    monkeypatch.setenv("BEDROCK_MODEL_ID", "model-b")
    second = build_config("1.0.0", "2026-10-30")
    assert first.config_hash() != second.config_hash()
