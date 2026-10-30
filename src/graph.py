from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langgraph.graph import END, START, StateGraph

from src.evidence import EvidenceError, build_extraction
from src.llm import Extractor
from src.logging import log_event
from src.prompts import PromptAsset
from src.schemas import (
    ClauseExtraction,
    ErrorRecord,
    GoldSpan,
    ModelClauseExtraction,
)
from src.states import ExtractionState


@dataclass
class GraphDeps:
    extractor: Extractor
    prompt: PromptAsset
    contract_id: str
    gold_spans: list[GoldSpan]
    model_id: str
    prompt_version: str
    created_at_utc: str
    prediction_writer: Callable[[ClauseExtraction], None]
    error_writer: Callable[[ErrorRecord], None]
    logger: logging.Logger | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_s: float = 0.0


def _schema_json() -> str:
    return json.dumps(ModelClauseExtraction.model_json_schema(), indent=2, sort_keys=True)


def _error_dict(
    error_type: str,
    reason: str,
    detail: str | None = None,
    *,
    predicted_value: str | None = None,
    quote: str | None = None,
    char_start: int | None = None,
    char_end: int | None = None,
) -> dict[str, Any]:
    return {
        "error_type": error_type,
        "reason": reason,
        "detail": detail,
        "predicted_value": predicted_value,
        "quote": quote,
        "char_start": char_start,
        "char_end": char_end,
    }


def build_graph(deps: GraphDeps) -> Any:
    def load_text(state: ExtractionState) -> dict[str, Any]:
        path = state.get("path")
        text = state.get("text") or ""
        if path:
            text = Path(path).read_text(encoding="utf-8")
        if deps.logger is not None:
            log_event(
                deps.logger,
                "contract_loaded",
                "contract text loaded",
                contract_id=deps.contract_id,
                text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                text_length=len(text),
            )
        if not text.strip():
            errors = list(state.get("errors", []))
            errors.append(_error_dict("operational_error", "empty_text", "contract text is empty"))
            return {"text": text, "errors": errors}
        return {"text": text}

    def extract(state: ExtractionState) -> dict[str, Any]:
        text = state.get("text", "")
        prompt = deps.prompt.render(_schema_json(), text)
        if deps.logger is not None:
            log_event(
                deps.logger,
                "prompt_rendered",
                "prompt rendered",
                contract_id=deps.contract_id,
                prompt_version=deps.prompt_version,
                prompt_sha256=deps.prompt.sha256,
            )
            log_event(
                deps.logger,
                "model_request",
                "model request sent",
                contract_id=deps.contract_id,
                model_id=deps.model_id,
                text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            )

        result = deps.extractor.extract(prompt)
        deps.input_tokens = result.input_tokens
        deps.output_tokens = result.output_tokens
        deps.cost_usd = result.cost_usd
        deps.latency_s = result.latency_s

        errors = list(state.get("errors", []))
        for error in result.errors:
            errors.append(
                _error_dict(
                    error.error_type,
                    error.reason,
                    error.detail,
                    predicted_value=result.output.value if result.output else None,
                    quote=result.output.quote if result.output else None,
                )
            )

        if deps.logger is not None:
            log_event(
                deps.logger,
                "model_response",
                "model response received",
                contract_id=deps.contract_id,
                status=result.output.status.value if result.output else None,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                latency_s=result.latency_s,
                cost_usd=result.cost_usd,
                error_count=len(result.errors),
            )

        fields = result.output.model_dump(mode="json") if result.output else None
        return {"fields": fields, "errors": errors}

    def validate(state: ExtractionState) -> dict[str, Any]:
        fields = state.get("fields")
        if not fields:
            return {}
        text = state.get("text", "")
        model_output = ModelClauseExtraction.model_validate(fields)
        try:
            enriched = build_extraction(model_output, deps.contract_id, text)
        except EvidenceError as exc:
            errors = list(state.get("errors", []))
            errors.append(
                _error_dict(
                    "invalid_output",
                    exc.reason,
                    exc.detail,
                    predicted_value=model_output.value,
                    quote=model_output.quote,
                )
            )
            if deps.logger is not None:
                log_event(
                    deps.logger,
                    "validation_failed",
                    "evidence validation failed",
                    contract_id=deps.contract_id,
                    reason=exc.reason,
                )
            return {"fields": None, "errors": errors}

        if deps.logger is not None:
            log_event(
                deps.logger,
                "evidence_derived",
                "evidence derived",
                contract_id=deps.contract_id,
                status=enriched.status.value,
                char_start=enriched.char_start,
                char_end=enriched.char_end,
            )
        return {"fields": enriched.model_dump(mode="json")}

    def persist(state: ExtractionState) -> dict[str, Any]:
        fields = state.get("fields")
        if fields:
            deps.prediction_writer(ClauseExtraction.model_validate(fields))
        for error in state.get("errors", []):
            deps.error_writer(
                ErrorRecord(
                    contract_id=deps.contract_id,
                    error_type=error["error_type"],
                    reason=error["reason"],
                    detail=error.get("detail"),
                    predicted_value=error.get("predicted_value"),
                    quote=error.get("quote"),
                    char_start=error.get("char_start"),
                    char_end=error.get("char_end"),
                    gold_spans=deps.gold_spans,
                    model_id=deps.model_id,
                    prompt_version=deps.prompt_version,
                    created_at_utc=deps.created_at_utc,
                )
            )
        return {}

    graph = StateGraph(ExtractionState)
    graph.add_node("load_text", load_text)
    graph.add_node("extract", extract)
    graph.add_node("validate", validate)
    graph.add_node("persist", persist)
    graph.add_edge(START, "load_text")
    graph.add_edge("load_text", "extract")
    graph.add_edge("extract", "validate")
    graph.add_edge("validate", "persist")
    graph.add_edge("persist", END)
    return graph.compile()
