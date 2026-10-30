from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, model_validator


class ClauseStatus(StrEnum):
    FOUND = "found"
    NOT_FOUND = "not_found"


class ModelClauseExtraction(BaseModel):
    clause_type: Literal["governing_law"]
    status: ClauseStatus
    value: str | None = None
    quote: str | None = None

    @model_validator(mode="after")
    def validate_evidence(self) -> "ModelClauseExtraction":
        if self.status is ClauseStatus.FOUND:
            if not self.value or not self.quote:
                raise ValueError("found clauses require a value and quote")
        elif self.value is not None or self.quote is not None:
            raise ValueError("not_found clauses must not carry a value or quote")
        return self


class ClauseExtraction(ModelClauseExtraction):
    contract_id: str
    char_start: int | None = None
    char_end: int | None = None

    @model_validator(mode="after")
    def validate_span(self) -> "ClauseExtraction":
        if self.status is ClauseStatus.FOUND:
            if self.char_start is None or self.char_end is None:
                raise ValueError("found clauses require a character span")
            if self.char_end <= self.char_start:
                raise ValueError("char_end must be greater than char_start")
        elif self.char_start is not None or self.char_end is not None:
            raise ValueError("not_found clauses must not carry a span")
        return self


class GoldSpan(BaseModel):
    char_start: int
    char_end: int


class ErrorType(StrEnum):
    INVALID_OUTPUT = "invalid_output"
    CONTEXT_OVERFLOW = "context_overflow"
    BUDGET_EXCEEDED = "budget_exceeded"
    OPERATIONAL_ERROR = "operational_error"


class ErrorRecord(BaseModel):
    contract_id: str
    error_type: Literal[
        "invalid_output",
        "context_overflow",
        "budget_exceeded",
        "operational_error",
    ]
    reason: str
    detail: str | None = None
    predicted_value: str | None = None
    quote: str | None = None
    char_start: int | None = None
    char_end: int | None = None
    gold_spans: list[GoldSpan] = []
    model_id: str | None = None
    prompt_version: str
    created_at_utc: str
