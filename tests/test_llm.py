import json

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from pydantic import ValidationError

from src.llm import (
    ExtractionResult,
    LangChainExtractor,
    StubExtractor,
    _classify_exception,
)
from src.schemas import ClauseStatus, ModelClauseExtraction

MODEL = "global.anthropic.claude-haiku-4-5-20251001-v1:0"


class FakeMessage:
    def __init__(self, usage_metadata: dict | None) -> None:
        self.usage_metadata = usage_metadata


class FakeStructured:
    def __init__(self, response: object) -> None:
        self.response = response

    def invoke(self, prompt: str) -> object:
        if isinstance(self.response, BaseException):
            raise self.response
        return self.response


def make_extractor(response: object) -> LangChainExtractor:
    extractor = object.__new__(LangChainExtractor)
    extractor.model_id = MODEL
    extractor.timeout_s = 60.0
    extractor._structured = FakeStructured(response)
    return extractor


def found_model() -> ModelClauseExtraction:
    return ModelClauseExtraction(
        clause_type="governing_law",
        status=ClauseStatus.FOUND,
        value="laws of Delaware",
        quote="laws of Delaware",
    )


def test_fake_found_response() -> None:
    response = {
        "parsed": found_model(),
        "raw": FakeMessage({"input_tokens": 1000, "output_tokens": 20}),
        "parsing_error": None,
    }
    result = make_extractor(response).extract("prompt")
    assert isinstance(result, ExtractionResult)
    assert result.output is not None
    assert result.input_tokens == 1000
    assert result.output_tokens == 20
    assert result.cost_usd == pytest.approx(0.0011, abs=1e-6)
    assert result.errors == []


def test_fake_not_found_response() -> None:
    response = {
        "parsed": ModelClauseExtraction(clause_type="governing_law", status="not_found"),
        "raw": FakeMessage({"input_tokens": 10, "output_tokens": 5}),
        "parsing_error": None,
    }
    result = make_extractor(response).extract("prompt")
    assert result.output is not None
    assert result.output.status is ClauseStatus.NOT_FOUND


def test_schema_error() -> None:
    response = {
        "parsed": None,
        "raw": FakeMessage({"input_tokens": 10, "output_tokens": 5}),
        "parsing_error": ValueError("bad"),
    }
    result = make_extractor(response).extract("prompt")
    assert result.output is None
    assert result.errors[0].error_type == "invalid_output"
    assert result.errors[0].reason == "schema_error"


def test_missing_usage() -> None:
    response = {"parsed": found_model(), "raw": FakeMessage(None), "parsing_error": None}
    result = make_extractor(response).extract("prompt")
    assert result.errors[0].error_type == "operational_error"
    assert result.errors[0].reason == "missing_usage"


def test_high_usage_keeps_prediction() -> None:
    response = {
        "parsed": found_model(),
        "raw": FakeMessage({"input_tokens": 1_000_000, "output_tokens": 0}),
        "parsing_error": None,
    }
    result = make_extractor(response).extract("prompt")
    assert result.output is not None
    assert any(error.reason == "cost" for error in result.errors)


def test_timeout() -> None:
    result = make_extractor(TimeoutError("slow")).extract("prompt")
    assert result.output is None
    assert result.errors[0].error_type == "budget_exceeded"
    assert result.errors[0].reason == "timeout"


def test_context_overflow() -> None:
    exc = ClientError(
        {"Error": {"Code": "ValidationException", "Message": "input is too long"}},
        "InvokeModel",
    )
    result = make_extractor(exc).extract("prompt")
    assert result.errors[0].error_type == "context_overflow"
    assert result.errors[0].reason == "input_too_long"


def test_auth_failure() -> None:
    exc = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
        "InvokeModel",
    )
    result = make_extractor(exc).extract("prompt")
    assert result.errors[0].error_type == "operational_error"
    assert result.errors[0].reason == "auth"


def test_network_failure() -> None:
    exc = EndpointConnectionError(endpoint_url="https://example.invalid")
    result = make_extractor(exc).extract("prompt")
    assert result.errors[0].error_type == "operational_error"
    assert result.errors[0].reason == "network"


def test_json_error_classification() -> None:
    error = _classify_exception(json.JSONDecodeError("bad", "x", 0))
    assert error.error_type == "invalid_output"
    assert error.reason == "json_error"


def test_validation_error_classification() -> None:
    with pytest.raises(ValidationError) as captured:
        ModelClauseExtraction(clause_type="governing_law", status="found")
    error = _classify_exception(captured.value)
    assert error.error_type == "invalid_output"
    assert error.reason == "schema_error"


def test_stub_is_deterministic() -> None:
    result = StubExtractor().extract("prompt")
    assert result.output is not None
    assert result.output.status is ClauseStatus.NOT_FOUND
    assert result.input_tokens == 0
    assert result.errors == []
