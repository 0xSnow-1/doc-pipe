import json
from pathlib import Path

from src.logging import close_logging, log_event, setup_run_logging


def test_jsonl_format_and_events(tmp_path: Path) -> None:
    logger = setup_run_logging("run-1", tmp_path)
    log_event(logger, "run_start", "started", contract_id="c")
    log_event(logger, "run_end", "finished", contract_id="c")
    close_logging(logger)
    lines = (tmp_path / "logs.jsonl").read_text().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["event"] == "run_start"
    assert first["run_id"] == "run-1"
    assert first["contract_id"] == "c"
    assert "timestamp_utc" in first
    assert "level" in first
    assert "message" in first


def test_secret_and_contract_text_are_not_logged(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LANGSMITH_API_KEY", "super-secret-value-123")
    contract_text = "This is the full contract text that must not be logged."
    logger = setup_run_logging("run-2", tmp_path, sensitive_text=contract_text)
    log_event(logger, "model_request", f"key super-secret-value-123 {contract_text}")
    close_logging(logger)
    blob = (tmp_path / "logs.jsonl").read_text()
    assert "super-secret-value-123" not in blob
    assert contract_text not in blob
    assert "[REDACTED]" in blob
    for line in blob.splitlines():
        json.loads(line)
