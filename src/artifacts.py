from __future__ import annotations

import contextlib
import json
import os
import secrets
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RUN_FILES = ("input.txt", "manifest.json", "predictions.jsonl", "errors.jsonl", "logs.jsonl")


class RunExistsError(Exception):
    pass


def utc_now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def generate_run_id(now: datetime | None = None) -> str:
    moment = now or datetime.now(UTC)
    return f"{moment.strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(4)}"


def create_run_dir(runs_dir: Path, run_id: str) -> Path:
    run_dir = runs_dir / run_id
    if run_dir.exists():
        raise RunExistsError(f"run folder already exists: {run_dir}")
    run_dir.mkdir(parents=True)
    return run_dir


def init_run_files(run_dir: Path) -> None:
    for name in ("predictions.jsonl", "errors.jsonl", "logs.jsonl"):
        (run_dir / name).touch()


def write_input(run_dir: Path, text: str) -> None:
    atomic_write_text(run_dir / "input.txt", text)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temp_name)
        raise


def append_jsonl(path: Path, record: dict[str, Any] | Any) -> None:
    if not isinstance(record, dict):
        if hasattr(record, "model_dump"):
            record = record.model_dump(mode="json")
        else:
            raise TypeError("JSONL records must be dicts or Pydantic models")
    line = json.dumps(record, ensure_ascii=False, default=str)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def write_manifest(run_dir: Path, manifest: dict[str, Any]) -> None:
    atomic_write_text(run_dir / "manifest.json", json.dumps(manifest, indent=2) + "\n")


def git_commit() -> str:
    root = Path(__file__).resolve().parents[1]
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return result.stdout.strip() or "unknown"
