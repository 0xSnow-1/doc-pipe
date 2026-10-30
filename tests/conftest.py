from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.data import ContractRecord, CuadDataset
from src.llm import ExtractionError, ExtractionResult
from src.schemas import ClauseStatus, GoldSpan, ModelClauseExtraction
from src.tracing import tracing_enabled

FIXTURES = Path(__file__).parent / "fixtures"
POSITIVE_QUOTE = "governed by the laws of the State of Delaware"
REPEATED_QUOTE = "Governed by the laws of New York."


class FakeExtractor:
    def __init__(self, result: ExtractionResult | BaseException) -> None:
        self.result = result
        self.prompts: list[str] = []

    def extract(self, prompt: str) -> ExtractionResult:
        self.prompts.append(prompt)
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


def found_result(quote: str = POSITIVE_QUOTE) -> ExtractionResult:
    return ExtractionResult(
        output=ModelClauseExtraction(
            clause_type="governing_law",
            status=ClauseStatus.FOUND,
            value=quote,
            quote=quote,
        ),
        input_tokens=1000,
        output_tokens=20,
        latency_s=0.5,
        cost_usd=0.0011,
    )


def not_found_result() -> ExtractionResult:
    return ExtractionResult(
        output=ModelClauseExtraction(
            clause_type="governing_law",
            status=ClauseStatus.NOT_FOUND,
        )
    )


@pytest.fixture
def cuad_small() -> dict[str, Any]:
    return json.loads((FIXTURES / "cuad_small.json").read_text())


@pytest.fixture
def cuad_small_path() -> Path:
    return FIXTURES / "cuad_small.json"


@pytest.fixture
def small_dataset(cuad_small_path: Path) -> CuadDataset:
    from src.data import load_cuad

    return load_cuad(cuad_small_path)


@pytest.fixture
def contract_positive() -> ContractRecord:
    text = (
        "This Agreement shall be governed by the laws of the State of Delaware. The parties agree."
    )
    start = text.index(POSITIVE_QUOTE)
    return ContractRecord(
        contract_id="Positive Contract",
        text=text,
        gold_spans=[GoldSpan(char_start=start, char_end=start + len(POSITIVE_QUOTE))],
    )


@pytest.fixture
def contract_negative() -> ContractRecord:
    return ContractRecord(
        contract_id="Negative Contract",
        text="The parties will meet quarterly to review the schedule.",
    )


@pytest.fixture
def contract_repeated_quote() -> ContractRecord:
    return ContractRecord(
        contract_id="Repeated Contract",
        text="Governed by the laws of New York. Governed by the laws of New York.",
        gold_spans=[GoldSpan(char_start=0, char_end=len(REPEATED_QUOTE))],
    )


@pytest.fixture
def fake_found() -> FakeExtractor:
    return FakeExtractor(found_result())


@pytest.fixture
def fake_not_found() -> FakeExtractor:
    return FakeExtractor(not_found_result())


@pytest.fixture
def fake_invalid_schema() -> FakeExtractor:
    return FakeExtractor(
        ExtractionResult(errors=[ExtractionError("invalid_output", "schema_error", "bad schema")])
    )


@pytest.fixture
def fake_duplicate_quote() -> FakeExtractor:
    return FakeExtractor(found_result(REPEATED_QUOTE))


@pytest.fixture
def fake_missing_quote() -> FakeExtractor:
    return FakeExtractor(found_result("text that is not in the contract"))


@pytest.fixture
def fake_timeout() -> FakeExtractor:
    return FakeExtractor(ExtractionResult(errors=[ExtractionError("budget_exceeded", "timeout")]))


@pytest.fixture
def fake_context_overflow() -> FakeExtractor:
    return FakeExtractor(
        ExtractionResult(errors=[ExtractionError("context_overflow", "input_too_long")])
    )


@pytest.fixture
def fake_auth_error() -> FakeExtractor:
    return FakeExtractor(ExtractionResult(errors=[ExtractionError("operational_error", "auth")]))


@pytest.fixture
def temp_runs_dir(tmp_path: Path) -> Path:
    runs = tmp_path / "runs"
    runs.mkdir()
    return runs


@pytest.fixture
def temp_data_dir(tmp_path: Path, cuad_small_path: Path) -> Path:
    data_dir = tmp_path / "data"
    (data_dir / "cache").mkdir(parents=True)
    (data_dir / "cache" / "CUAD_v1.json").write_text(cuad_small_path.read_text())
    return data_dir


@pytest.fixture
def no_langsmith(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "LANGSMITH_TRACING",
        "LANGSMITH_API_KEY",
        "LANGCHAIN_TRACING_V2",
        "LANGCHAIN_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    assert tracing_enabled() is False
