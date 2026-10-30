from __future__ import annotations

import tomllib
from pathlib import Path

PRICING_PATH = Path(__file__).resolve().parents[1] / "config" / "pricing.toml"
MAX_COST_USD = 0.50


class PricingError(Exception):
    pass


def load_pricing(path: Path = PRICING_PATH) -> dict[str, object]:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise PricingError(f"cannot read pricing table at {path}: {exc}") from exc


def pricing_version(path: Path = PRICING_PATH) -> str:
    table = load_pricing(path)
    version = table.get("version")
    if not isinstance(version, str) or not version:
        raise PricingError("pricing table is missing a version")
    return version


def compute_cost(
    model_id: str,
    input_tokens: int,
    output_tokens: int,
    path: Path = PRICING_PATH,
) -> float:
    table = load_pricing(path)
    models = table.get("models")
    if not isinstance(models, dict) or model_id not in models:
        raise PricingError(f"unknown model in pricing table: {model_id}")
    rates = models[model_id]
    if not isinstance(rates, dict):
        raise PricingError(f"pricing entry for {model_id} is malformed")
    try:
        input_rate = float(rates["input_per_million_usd"])
        output_rate = float(rates["output_per_million_usd"])
    except (KeyError, TypeError, ValueError) as exc:
        raise PricingError(f"pricing entry for {model_id} is malformed") from exc
    return (input_tokens / 1_000_000) * input_rate + (output_tokens / 1_000_000) * output_rate
