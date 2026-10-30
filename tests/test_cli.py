from pathlib import Path

import pytest

from src.cli import main
from src.data import Split


def test_help() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0


def test_missing_contract_id() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["run"])
    assert exc.value.code == 2


def test_unknown_contract(
    monkeypatch: pytest.MonkeyPatch, cuad_small_path: Path, tmp_path: Path
) -> None:
    monkeypatch.setattr("src.cli.download_cuad", lambda *args, **kwargs: cuad_small_path)
    code = main(
        [
            "run",
            "--contract-id",
            "does-not-exist",
            "--stub",
            "--runs-dir",
            str(tmp_path / "runs"),
            "--data-dir",
            str(tmp_path / "data"),
        ]
    )
    assert code == 2
    assert not (tmp_path / "runs").exists()


def test_missing_model_id_live_mode(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("src.cli.load_environment", lambda: None)
    monkeypatch.delenv("BEDROCK_MODEL_ID", raising=False)
    code = main(
        [
            "run",
            "--contract-id",
            "Positive Contract",
            "--runs-dir",
            str(tmp_path / "runs"),
            "--data-dir",
            str(tmp_path / "data"),
        ]
    )
    assert code == 2
    assert not (tmp_path / "runs").exists()


def test_run_stub_creates_files(
    monkeypatch: pytest.MonkeyPatch, cuad_small_path: Path, tmp_path: Path
) -> None:
    monkeypatch.setattr("src.cli.download_cuad", lambda *args, **kwargs: cuad_small_path)
    runs_dir = tmp_path / "runs"
    code = main(
        [
            "run",
            "--contract-id",
            "Positive Contract",
            "--stub",
            "--run-id",
            "run-1",
            "--runs-dir",
            str(runs_dir),
            "--data-dir",
            str(tmp_path / "data"),
        ]
    )
    assert code == 0
    run_dir = runs_dir / "run-1"
    for name in ("input.txt", "manifest.json", "predictions.jsonl", "errors.jsonl", "logs.jsonl"):
        assert (run_dir / name).exists()
    predictions = (run_dir / "predictions.jsonl").read_text().strip()
    assert '"not_found"' in predictions


def test_existing_run_folder_is_rejected(
    monkeypatch: pytest.MonkeyPatch, cuad_small_path: Path, tmp_path: Path
) -> None:
    monkeypatch.setattr("src.cli.download_cuad", lambda *args, **kwargs: cuad_small_path)
    args = [
        "run",
        "--contract-id",
        "Positive Contract",
        "--stub",
        "--run-id",
        "run-1",
        "--runs-dir",
        str(tmp_path / "runs"),
        "--data-dir",
        str(tmp_path / "data"),
    ]
    assert main(args) == 0
    assert main(args) == 2


def test_verify_data_with_mocked_download(
    monkeypatch: pytest.MonkeyPatch, cuad_small_path: Path, tmp_path: Path, capsys
) -> None:
    report = {
        "counts": {
            "contracts": 510,
            "clause_types": 41,
            "governing_law_entries": 510,
            "contracts_with_span": 437,
            "contracts_without_span": 73,
            "gold_spans": 464,
            "max_gold_spans": 4,
        },
        "split": {"eval": 10, "dev": 10, "overlap": 0},
    }
    monkeypatch.setattr("src.cli.download_cuad", lambda *args, **kwargs: cuad_small_path)
    monkeypatch.setattr("src.cli.load_cuad", lambda path: object())
    monkeypatch.setattr("src.cli.load_split", lambda path: Split(eval=[], dev=[]))
    monkeypatch.setattr("src.cli.validate_dataset", lambda dataset: [])
    monkeypatch.setattr("src.cli.validate_split", lambda split, dataset: [])
    monkeypatch.setattr(
        "src.cli.write_data_report",
        lambda report_path, dataset, split, failures: report,
    )
    code = main(["verify-data", "--split", str(tmp_path / "split.json")])
    assert code == 0
    out = capsys.readouterr().out
    assert "contracts: 510" in out
    assert "governing-law gold spans: 464" in out
