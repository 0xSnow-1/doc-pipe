from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import (
    ClientError,
    EndpointConnectionError,
    NoCredentialsError,
    PartialCredentialsError,
    ReadTimeoutError,
)
from botocore.exceptions import (
    ConnectionError as BotoConnectionError,
)
from pydantic import ValidationError

from src.pricing import MAX_COST_USD, PricingError, compute_cost
from src.schemas import ClauseStatus, ModelClauseExtraction

DEFAULT_TIMEOUT_S = 60.0
DEFAULT_MAX_TOKENS = 1024


@dataclass(frozen=True)
class ExtractionError:
    error_type: str
    reason: str
    detail: str | None = None


@dataclass
class ExtractionResult:
    output: ModelClauseExtraction | None = None
    errors: list[ExtractionError] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    latency_s: float = 0.0
    cost_usd: float = 0.0


class Extractor(Protocol):
    def extract(self, prompt: str) -> ExtractionResult: ...


def _classify_exception(exc: BaseException) -> ExtractionError:
    if isinstance(exc, ValidationError):
        return ExtractionError("invalid_output", "schema_error", str(exc))
    if isinstance(exc, json.JSONDecodeError):
        return ExtractionError("invalid_output", "json_error", str(exc))
    if isinstance(exc, (ReadTimeoutError, TimeoutError)):
        return ExtractionError("budget_exceeded", "timeout", str(exc))
    if isinstance(exc, (NoCredentialsError, PartialCredentialsError)):
        return ExtractionError("operational_error", "auth", str(exc))
    if isinstance(exc, (BotoConnectionError, EndpointConnectionError)):
        return ExtractionError("operational_error", "network", str(exc))
    if isinstance(exc, ClientError):
        code = str(exc.response.get("Error", {}).get("Code", ""))
        message = str(exc.response.get("Error", {}).get("Message", ""))
        lowered = message.lower()
        if code in {
            "AccessDeniedException",
            "UnauthorizedException",
            "UnrecognizedClientException",
            "InvalidSignatureException",
            "ExpiredTokenException",
        }:
            return ExtractionError("operational_error", "auth", message)
        if code in {
            "ThrottlingException",
            "TooManyRequestsException",
            "ServiceQuotaExceededException",
        }:
            return ExtractionError("operational_error", "throttled", message)
        if code in {"ModelTimeoutException"}:
            return ExtractionError("budget_exceeded", "timeout", message)
        if code == "ValidationException" and (
            "too long" in lowered or "too many tokens" in lowered or "input length" in lowered
        ):
            return ExtractionError("context_overflow", "input_too_long", message)
        return ExtractionError("operational_error", "unknown", f"{code}: {message}")
    return ExtractionError("operational_error", "unknown", str(exc))


class LangChainExtractor:
    def __init__(
        self,
        model_id: str,
        region: str,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        from langchain_aws import ChatBedrock

        self.model_id = model_id
        self.timeout_s = timeout_s
        client = boto3.client(
            "bedrock-runtime",
            region_name=region,
            config=Config(
                connect_timeout=10,
                read_timeout=timeout_s,
                retries={"max_attempts": 0},
            ),
        )
        llm = ChatBedrock(
            model=model_id,
            region=region,
            client=client,
            model_kwargs={"temperature": 0.0, "max_tokens": max_tokens},
        )
        self._structured = llm.with_structured_output(ModelClauseExtraction, include_raw=True)

    def extract(self, prompt: str) -> ExtractionResult:
        started = time.monotonic()
        try:
            response = self._structured.invoke(prompt)
        except Exception as exc:
            return ExtractionResult(errors=[_classify_exception(exc)])

        latency = time.monotonic() - started
        parsed = response.get("parsed") if isinstance(response, dict) else response
        raw_message = response.get("raw") if isinstance(response, dict) else None
        parsing_error = response.get("parsing_error") if isinstance(response, dict) else None

        if parsing_error is not None:
            return ExtractionResult(
                errors=[ExtractionError("invalid_output", "schema_error", str(parsing_error))],
                latency_s=latency,
            )
        if not isinstance(parsed, ModelClauseExtraction):
            return ExtractionResult(
                errors=[
                    ExtractionError("invalid_output", "schema_error", "unexpected output shape")
                ],
                latency_s=latency,
            )

        usage = getattr(raw_message, "usage_metadata", None) or {}
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        if not isinstance(input_tokens, int) or not isinstance(output_tokens, int):
            return ExtractionResult(
                output=parsed,
                errors=[ExtractionError("operational_error", "missing_usage", None)],
                latency_s=latency,
            )

        errors: list[ExtractionError] = []
        try:
            cost = compute_cost(self.model_id, input_tokens, output_tokens)
        except PricingError as exc:
            return ExtractionResult(
                output=parsed,
                errors=[ExtractionError("operational_error", "unknown", str(exc))],
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_s=latency,
            )
        if cost > MAX_COST_USD:
            errors.append(
                ExtractionError(
                    "budget_exceeded", "cost", f"cost {cost:.6f} exceeds {MAX_COST_USD}"
                )
            )
        if latency > self.timeout_s:
            errors.append(
                ExtractionError(
                    "budget_exceeded", "timeout", f"latency {latency:.2f}s exceeds {self.timeout_s}"
                )
            )

        return ExtractionResult(
            output=parsed,
            errors=errors,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_s=latency,
            cost_usd=cost,
        )


class StubExtractor:
    def extract(self, prompt: str) -> ExtractionResult:
        return ExtractionResult(
            output=ModelClauseExtraction(
                clause_type="governing_law",
                status=ClauseStatus.NOT_FOUND,
            )
        )


def build_extractor(stub: bool, model_id: str | None, region: str) -> Extractor:
    if stub:
        return StubExtractor()
    if not model_id:
        raise ValueError("model_id is required for live extraction")
    return LangChainExtractor(model_id=model_id, region=region)
