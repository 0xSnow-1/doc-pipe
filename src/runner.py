from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.artifacts import (
    append_jsonl,
    create_run_dir,
    generate_run_id,
    git_commit,
    init_run_files,
    utc_now_iso,
    write_input,
    write_manifest,
)
from src.config import RuntimeConfig
from src.data import ContractRecord
from src.graph import GraphDeps, build_graph
from src.llm import build_extractor
from src.logging import close_logging, log_event, setup_run_logging
from src.prompts import PromptAsset, load_prompt
from src.schemas import ClauseExtraction, ErrorRecord
from src.states import new_state

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class RunResult:
    run_id: str
    run_dir: Path
    exit_code: int
    manifest: dict[str, Any]


def _manifest_contract(
    contract_id: str,
    status: str,
    deps: GraphDeps,
    errors: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "contract_id": contract_id,
        "prediction_status": status,
        "input_tokens": deps.input_tokens,
        "output_tokens": deps.output_tokens,
        "cost_usd": round(deps.cost_usd, 6),
        "latency_s": round(deps.latency_s, 4),
        "errors": [error["reason"] for error in errors],
    }


def run_contract(
    contract: ContractRecord,
    config: RuntimeConfig,
    run_id: str | None = None,
    runs_dir: Path | None = None,
    stub: bool = False,
    prompt: PromptAsset | None = None,
    stream: Any | None = None,
) -> RunResult:
    runs_dir = runs_dir or ROOT / "runs"
    run_id = run_id or generate_run_id()
    prompt = prompt or load_prompt()
    created_at = utc_now_iso()

    run_dir = create_run_dir(runs_dir, run_id)
    write_input(run_dir, contract.text)
    init_run_files(run_dir)
    logger = setup_run_logging(run_id, run_dir, stream=stream, sensitive_text=contract.text)

    log_event(
        logger,
        "run_start",
        "run started",
        contract_id=contract.contract_id,
        model_id=config.model_id,
        stub=stub,
    )

    extractor = build_extractor(stub, config.model_id, config.region)
    deps = GraphDeps(
        extractor=extractor,
        prompt=prompt,
        contract_id=contract.contract_id,
        gold_spans=contract.gold_spans,
        model_id=config.model_id,
        prompt_version=prompt.version,
        created_at_utc=created_at,
        prediction_writer=lambda record: append_jsonl(run_dir / "predictions.jsonl", record),
        error_writer=lambda record: append_jsonl(run_dir / "errors.jsonl", record),
        logger=logger,
    )

    state = new_state(str(run_dir / "input.txt"), contract.text)
    fatal = False
    final_state: dict[str, Any]
    try:
        final_state = build_graph(deps).invoke(state)
    except Exception as exc:
        final_state = dict(state)
        error = {
            "error_type": "operational_error",
            "reason": "unknown",
            "detail": str(exc),
            "predicted_value": None,
            "quote": None,
            "char_start": None,
            "char_end": None,
        }
        final_state["errors"] = [*final_state.get("errors", []), error]
        deps.error_writer(
            ErrorRecord(
                contract_id=contract.contract_id,
                error_type="operational_error",
                reason="unknown",
                detail=str(exc),
                gold_spans=contract.gold_spans,
                model_id=config.model_id,
                prompt_version=prompt.version,
                created_at_utc=created_at,
            )
        )
        fatal = True

    errors = list(final_state.get("errors", []))
    fields = final_state.get("fields")
    if fields:
        status = ClauseExtraction.model_validate(fields).status.value
    else:
        status = "error"
        fatal = fatal or any(error["error_type"] == "operational_error" for error in errors)

    run_status = "failed" if fatal else "completed"
    manifest = {
        "run_id": run_id,
        "timestamp_utc": created_at,
        "git_commit": git_commit(),
        "model_id": config.model_id,
        "prompt_version": prompt.version,
        "prompt_sha256": prompt.sha256,
        "dataset_revision": config.dataset_revision,
        "input_mode": config.input_mode,
        "config_hash": config.config_hash(),
        "pricing_version": config.pricing_version,
        "total_cost_usd": round(deps.cost_usd, 6),
        "total_latency_s": round(deps.latency_s, 4),
        "run_status": run_status,
        "contracts": [_manifest_contract(contract.contract_id, status, deps, errors)],
    }
    write_manifest(run_dir, manifest)
    log_event(
        logger,
        "artifacts_written",
        "run artifacts written",
        contract_id=contract.contract_id,
        run_status=run_status,
    )
    log_event(
        logger,
        "run_end",
        "run finished",
        contract_id=contract.contract_id,
        run_status=run_status,
        exit_code=1 if fatal else 0,
    )
    close_logging(logger)

    return RunResult(run_id=run_id, run_dir=run_dir, exit_code=1 if fatal else 0, manifest=manifest)
