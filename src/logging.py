from __future__ import annotations

import json
import logging
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RESERVED_KEYS = {"timestamp_utc", "level", "event", "run_id", "message", "contract_id"}
SECRET_NAME = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD)", re.IGNORECASE)
SECRET_ASSIGNMENT = re.compile(r"\b[A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD)[A-Z0-9_]*=\S+")


def _secret_values() -> list[str]:
    values = []
    for name, value in os.environ.items():
        if SECRET_NAME.search(name) and len(value) >= 8:
            values.append(value)
    return sorted(set(values), key=len, reverse=True)


def redact(text: str) -> str:
    for value in _secret_values():
        text = text.replace(value, "[REDACTED]")
    return SECRET_ASSIGNMENT.sub("[REDACTED]", text)


class JsonFormatter(logging.Formatter):
    def __init__(self, run_id: str, sensitive_text: str | None = None) -> None:
        super().__init__()
        self.run_id = run_id
        self.sensitive_text = sensitive_text

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp_utc": datetime.fromtimestamp(record.created, UTC).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "level": record.levelname,
            "event": getattr(record, "event", "log"),
            "run_id": getattr(record, "run_id", self.run_id),
            "message": record.getMessage(),
        }
        contract_id = getattr(record, "contract_id", None)
        if contract_id is not None:
            payload["contract_id"] = contract_id
        data = getattr(record, "data", None)
        if isinstance(data, dict):
            for key, value in data.items():
                if key not in RESERVED_KEYS:
                    payload[key] = value
        rendered = redact(json.dumps(payload, ensure_ascii=False, default=str))
        if self.sensitive_text:
            rendered = rendered.replace(self.sensitive_text, "[CONTRACT_TEXT_REDACTED]")
        return rendered


def setup_run_logging(
    run_id: str,
    run_dir: Path,
    stream: Any | None = None,
    sensitive_text: str | None = None,
) -> logging.Logger:
    logger = logging.getLogger(f"doc_pipe.{run_id}")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)

    formatter = JsonFormatter(run_id, sensitive_text)
    stream_handler = logging.StreamHandler(stream or sys.stderr)
    stream_handler.setFormatter(formatter)
    file_handler = logging.FileHandler(run_dir / "logs.jsonl", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    return logger


def close_logging(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)


def log_event(
    logger: logging.Logger,
    event: str,
    message: str,
    *,
    contract_id: str | None = None,
    **data: Any,
) -> None:
    logger.info(
        message,
        extra={
            "event": event,
            "contract_id": contract_id,
            "data": data,
        },
    )
