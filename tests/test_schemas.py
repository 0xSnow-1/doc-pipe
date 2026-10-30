import pytest
from pydantic import ValidationError

from src.schemas import ClauseExtraction, ClauseStatus, ModelClauseExtraction


def test_found_with_value_and_quote_round_trips() -> None:
    model = ModelClauseExtraction(
        clause_type="governing_law",
        status=ClauseStatus.FOUND,
        value="laws of Delaware",
        quote="laws of Delaware",
    )
    assert model.model_dump()["status"] == "found"


@pytest.mark.parametrize(
    "payload",
    [
        {"clause_type": "governing_law", "status": "found", "quote": "x"},
        {"clause_type": "governing_law", "status": "found", "value": "x"},
        {"clause_type": "governing_law", "status": "found", "value": "", "quote": ""},
    ],
)
def test_found_without_evidence_is_rejected(payload: dict) -> None:
    with pytest.raises(ValidationError):
        ModelClauseExtraction(**payload)


@pytest.mark.parametrize(
    "payload",
    [
        {"clause_type": "governing_law", "status": "not_found", "value": "x"},
        {"clause_type": "governing_law", "status": "not_found", "quote": "x"},
    ],
)
def test_not_found_with_evidence_is_rejected(payload: dict) -> None:
    with pytest.raises(ValidationError):
        ModelClauseExtraction(**payload)


def test_not_found_round_trips() -> None:
    model = ModelClauseExtraction(clause_type="governing_law", status="not_found")
    assert model.model_dump() == {
        "clause_type": "governing_law",
        "status": "not_found",
        "value": None,
        "quote": None,
    }


def test_found_without_span_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ClauseExtraction(
            contract_id="c",
            clause_type="governing_law",
            status="found",
            value="v",
            quote="q",
        )


def test_span_end_must_exceed_start() -> None:
    with pytest.raises(ValidationError):
        ClauseExtraction(
            contract_id="c",
            clause_type="governing_law",
            status="found",
            value="v",
            quote="q",
            char_start=5,
            char_end=5,
        )


def test_not_found_with_span_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ClauseExtraction(
            contract_id="c",
            clause_type="governing_law",
            status="not_found",
            char_start=1,
            char_end=2,
        )


def test_valid_found_extraction_round_trips() -> None:
    model = ClauseExtraction(
        contract_id="c",
        clause_type="governing_law",
        status="found",
        value="v",
        quote="q",
        char_start=1,
        char_end=2,
    )
    assert model.model_dump()["char_start"] == 1
