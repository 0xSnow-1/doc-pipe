import json
from pathlib import Path

from src.artifacts import append_jsonl
from src.data import ContractRecord
from src.graph import GraphDeps, build_graph
from src.llm import ExtractionResult
from src.prompts import load_prompt
from src.schemas import ModelClauseExtraction
from src.states import new_state

ROOT = Path(__file__).resolve().parents[1]


def run_graph(extractor: object, contract: ContractRecord, tmp_path: Path):
    input_path = tmp_path / "input.txt"
    input_path.write_text(contract.text)
    predictions = tmp_path / "predictions.jsonl"
    errors = tmp_path / "errors.jsonl"
    predictions.touch()
    errors.touch()
    deps = GraphDeps(
        extractor=extractor,
        prompt=load_prompt(),
        contract_id=contract.contract_id,
        gold_spans=contract.gold_spans,
        model_id="test-model",
        prompt_version="1.0.0",
        created_at_utc="2026-10-30T00:00:00Z",
        prediction_writer=lambda record: append_jsonl(predictions, record),
        error_writer=lambda record: append_jsonl(errors, record),
    )
    final = build_graph(deps).invoke(new_state(str(input_path)))
    return final, predictions, errors


def read_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_found_writes_prediction(fake_found, contract_positive, tmp_path: Path) -> None:
    _, predictions, errors = run_graph(fake_found, contract_positive, tmp_path)
    rows = read_rows(predictions)
    assert len(rows) == 1
    assert rows[0]["status"] == "found"
    assert contract_positive.text[rows[0]["char_start"] : rows[0]["char_end"]] == rows[0]["quote"]
    assert read_rows(errors) == []


def test_not_found_writes_prediction(fake_not_found, contract_negative, tmp_path: Path) -> None:
    _, predictions, errors = run_graph(fake_not_found, contract_negative, tmp_path)
    rows = read_rows(predictions)
    assert len(rows) == 1
    assert rows[0]["status"] == "not_found"
    assert rows[0]["char_start"] is None
    assert read_rows(errors) == []


def test_duplicate_quote_is_rejected(
    fake_duplicate_quote, contract_repeated_quote, tmp_path: Path
) -> None:
    _, predictions, errors = run_graph(fake_duplicate_quote, contract_repeated_quote, tmp_path)
    assert read_rows(predictions) == []
    rows = read_rows(errors)
    assert len(rows) == 1
    assert rows[0]["error_type"] == "invalid_output"
    assert rows[0]["reason"] == "quote_not_unique"


def test_missing_quote_is_rejected(fake_missing_quote, contract_positive, tmp_path: Path) -> None:
    _, predictions, errors = run_graph(fake_missing_quote, contract_positive, tmp_path)
    assert read_rows(predictions) == []
    assert read_rows(errors)[0]["reason"] == "quote_not_found"


def test_schema_failure_is_rejected(fake_invalid_schema, contract_positive, tmp_path: Path) -> None:
    _, predictions, errors = run_graph(fake_invalid_schema, contract_positive, tmp_path)
    assert read_rows(predictions) == []
    assert read_rows(errors)[0]["reason"] == "schema_error"


def test_context_overflow_is_recorded(
    fake_context_overflow, contract_positive, tmp_path: Path
) -> None:
    _, predictions, errors = run_graph(fake_context_overflow, contract_positive, tmp_path)
    assert read_rows(predictions) == []
    assert read_rows(errors)[0]["error_type"] == "context_overflow"


def test_timeout_is_recorded(fake_timeout, contract_positive, tmp_path: Path) -> None:
    _, predictions, errors = run_graph(fake_timeout, contract_positive, tmp_path)
    assert read_rows(predictions) == []
    assert read_rows(errors)[0]["reason"] == "timeout"


def test_auth_failure_is_recorded(fake_auth_error, contract_positive, tmp_path: Path) -> None:
    _, predictions, errors = run_graph(fake_auth_error, contract_positive, tmp_path)
    assert read_rows(predictions) == []
    assert read_rows(errors)[0]["reason"] == "auth"


def test_graph_source_has_no_conditional_edges() -> None:
    source = (ROOT / "src" / "graph.py").read_text()
    assert "add_conditional_edges" not in source
    assert "while " not in source


def test_budget_error_keeps_prediction(contract_positive, tmp_path: Path) -> None:
    from src.llm import ExtractionError

    class BudgetExtractor:
        def extract(self, prompt: str) -> ExtractionResult:
            result = ExtractionResult(
                output=ModelClauseExtraction(
                    clause_type="governing_law",
                    status="found",
                    value="governed by the laws of the State of Delaware",
                    quote="governed by the laws of the State of Delaware",
                ),
                errors=[ExtractionError("budget_exceeded", "cost")],
            )
            return result

    _, predictions, errors = run_graph(BudgetExtractor(), contract_positive, tmp_path)
    assert len(read_rows(predictions)) == 1
    assert read_rows(errors)[0]["reason"] == "cost"
