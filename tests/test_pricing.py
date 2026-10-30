import pytest

from src.pricing import PricingError, compute_cost, pricing_version

MODEL = "global.anthropic.claude-haiku-4-5-20251001-v1:0"


def test_input_only() -> None:
    assert compute_cost(MODEL, 1_000_000, 0) == pytest.approx(1.0, abs=1e-6)


def test_output_only() -> None:
    assert compute_cost(MODEL, 0, 1_000_000) == pytest.approx(5.0, abs=1e-6)


def test_mixed() -> None:
    assert compute_cost(MODEL, 12000, 80) == pytest.approx(0.0124, abs=1e-6)


def test_regional_rates() -> None:
    model = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    assert compute_cost(model, 1_000_000, 1_000_000) == pytest.approx(6.6, abs=1e-6)


def test_unknown_model() -> None:
    with pytest.raises(PricingError, match="unknown model"):
        compute_cost("not-a-model", 1, 1)


def test_pricing_version() -> None:
    assert pricing_version() == "2026-10-30"
