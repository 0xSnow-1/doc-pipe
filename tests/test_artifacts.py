import json
import re
from pathlib import Path

import pytest

from src.artifacts import (
    RunExistsError,
    append_jsonl,
    atomic_write_text,
    create_run_dir,
    generate_run_id,
    git_commit,
    init_run_files,
    write_manifest,
)


def test_create_run_dir(tmp_path: Path) -> None:
    run_dir = create_run_dir(tmp_path, "run-1")
    assert run_dir.is_dir()


def test_existing_run_dir_is_rejected(tmp_path: Path) -> None:
    create_run_dir(tmp_path, "run-1")
    with pytest.raises(RunExistsError):
        create_run_dir(tmp_path, "run-1")


def test_atomic_write_replaces_file(tmp_path: Path) -> None:
    path = tmp_path / "file.txt"
    atomic_write_text(path, "one")
    atomic_write_text(path, "two")
    assert path.read_text() == "two"
    assert not list(tmp_path.glob(".*.tmp"))


def test_append_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "rows.jsonl"
    append_jsonl(path, {"a": 1})
    append_jsonl(path, {"b": 2})
    lines = path.read_text().splitlines()
    assert [json.loads(line) for line in lines] == [{"a": 1}, {"b": 2}]


def test_run_id_format() -> None:
    assert re.fullmatch(r"\d{8}T\d{6}Z-[0-9a-f]{8}", generate_run_id())


def test_init_run_files(tmp_path: Path) -> None:
    init_run_files(tmp_path)
    assert (tmp_path / "predictions.jsonl").exists()
    assert (tmp_path / "errors.jsonl").exists()
    assert (tmp_path / "logs.jsonl").exists()


def test_write_manifest(tmp_path: Path) -> None:
    write_manifest(tmp_path, {"run_id": "x"})
    assert json.loads((tmp_path / "manifest.json").read_text()) == {"run_id": "x"}


def test_git_commit_returns_string() -> None:
    assert isinstance(git_commit(), str)
