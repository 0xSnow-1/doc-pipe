import io
import json
from pathlib import Path

from src.config import RuntimeConfig
from src.data import ContractRecord
from src.runner import run_contract
from src.schemas import GoldSpan

QUOTE = "governed by the laws of the State of Delaware"


def config() -> RuntimeConfig:
    return RuntimeConfig(
        model_id="stub",
        region="us-east-1",
        dataset_revision="a3c393f5d103fd0c516374e4fdff676c8176dcb1",
        input_mode="plain_text",
        prompt_version="1.0.0",
        pricing_version="2026-10-30",
    )


def contract() -> ContractRecord:
    text = f"This Agreement shall be {QUOTE}. The parties agree."
    start = text.index(QUOTE)
    return ContractRecord(
        contract_id="Positive Contract",
        text=text,
        gold_spans=[GoldSpan(char_start=start, char_end=start + len(QUOTE))],
    )


def read_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_stub_run_end_to_end(temp_runs_dir: Path) -> None:
    result = run_contract(
        contract(),
        config(),
        run_id="run-e2e",
        runs_dir=temp_runs_dir,
        stub=True,
        stream=io.StringIO(),
    )
    assert result.exit_code == 0
    run_dir = result.run_dir
    for name in ("input.txt", "manifest.json", "predictions.jsonl", "errors.jsonl", "logs.jsonl"):
        assert (run_dir / name).exists()

    predictions = read_rows(run_dir / "predictions.jsonl")
    assert len(predictions) == 1
    assert predictions[0]["status"] == "not_found"
    assert predictions[0]["char_start"] is None
    assert read_rows(run_dir / "errors.jsonl") == []

    manifest = json.loads((run_dir / "manifest.json").read_text())
    for key in (
        "run_id",
        "timestamp_utc",
        "git_commit",
        "model_id",
        "prompt_version",
        "prompt_sha256",
        "dataset_revision",
        "input_mode",
        "config_hash",
        "pricing_version",
        "total_cost_usd",
        "total_latency_s",
        "run_status",
        "contracts",
    ):
        assert key in manifest
    assert manifest["run_status"] == "completed"

    events = [row["event"] for row in read_rows(run_dir / "logs.jsonl")]
    for event in (
        "run_start",
        "contract_loaded",
        "prompt_rendered",
        "model_request",
        "model_response",
        "evidence_derived",
        "artifacts_written",
        "run_end",
    ):
        assert event in events


def test_found_prediction_slice_matches_quote(temp_runs_dir: Path, fake_found, monkeypatch) -> None:
    monkeypatch.setattr("src.runner.build_extractor", lambda *args, **kwargs: fake_found)
    result = run_contract(
        contract(),
        config(),
        run_id="run-found",
        runs_dir=temp_runs_dir,
        stub=True,
        stream=io.StringIO(),
    )
    predictions = read_rows(result.run_dir / "predictions.jsonl")
    assert len(predictions) == 1
    row = predictions[0]
    assert row["status"] == "found"
    assert contract().text[row["char_start"] : row["char_end"]] == row["quote"]
