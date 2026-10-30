from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from src.data import CUAD_REVISION

DEFAULT_REGION = "us-east-1"
INPUT_MODE = "plain_text"


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class RuntimeConfig:
    model_id: str
    region: str
    dataset_revision: str
    input_mode: str
    prompt_version: str
    pricing_version: str

    def config_hash(self) -> str:
        import hashlib
        import json

        payload = {
            "dataset_revision": self.dataset_revision,
            "input_mode": self.input_mode,
            "model_id": self.model_id,
            "pricing_version": self.pricing_version,
            "prompt_version": self.prompt_version,
            "region": self.region,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


def load_environment(env_file: Path | None = None) -> None:
    load_dotenv(dotenv_path=env_file, override=False)


def read_model_id() -> str | None:
    value = os.environ.get("BEDROCK_MODEL_ID", "").strip()
    return value or None


def build_config(prompt_version: str, pricing_version: str) -> RuntimeConfig:
    model_id = read_model_id()
    if model_id is None:
        raise ConfigError("BEDROCK_MODEL_ID is required for live runs")
    region = os.environ.get("BEDROCK_REGION", DEFAULT_REGION).strip() or DEFAULT_REGION
    return RuntimeConfig(
        model_id=model_id,
        region=region,
        dataset_revision=CUAD_REVISION,
        input_mode=INPUT_MODE,
        prompt_version=prompt_version,
        pricing_version=pricing_version,
    )
