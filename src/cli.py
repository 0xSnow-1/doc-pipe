from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.artifacts import RunExistsError
from src.config import ConfigError, RuntimeConfig, build_config, load_environment, read_model_id
from src.data import (
    CUAD_REVISION,
    DatasetError,
    download_cuad,
    load_cuad,
    load_split,
    validate_dataset,
    validate_split,
    write_data_report,
)
from src.pricing import PricingError, pricing_version
from src.prompts import PromptError, load_prompt
from src.runner import run_contract
from src.tracing import configure_tracing

ROOT = Path(__file__).resolve().parents[1]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="doc-pipe", description="Evidence-first contract extraction"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify = subparsers.add_parser("verify-data", help="verify the pinned CUAD dataset and split")
    verify.add_argument("--revision", default=CUAD_REVISION)
    verify.add_argument("--cache-dir", type=Path, default=ROOT / "data" / "cache")
    verify.add_argument("--report", type=Path, default=ROOT / "data" / "data_report.json")
    verify.add_argument("--split", type=Path, default=ROOT / "data" / "split.json")

    run = subparsers.add_parser("run", help="run governing-law extraction for one contract")
    run.add_argument("--contract-id", required=True)
    run.add_argument("--stub", action="store_true", help="use the offline deterministic stub")
    run.add_argument("--run-id")
    run.add_argument("--runs-dir", type=Path, default=ROOT / "runs")
    run.add_argument("--data-dir", type=Path, default=ROOT / "data")
    return parser


def _print_verify_summary(report: dict) -> None:
    counts = report["counts"]
    split = report["split"]
    print(f"contracts: {counts['contracts']}")
    print(f"clause types: {counts['clause_types']}")
    print(f"governing-law entries: {counts['governing_law_entries']}")
    print(f"contracts with a governing-law span: {counts['contracts_with_span']}")
    print(f"contracts with no governing-law span: {counts['contracts_without_span']}")
    print(f"governing-law gold spans: {counts['gold_spans']}")
    print(f"maximum gold spans on one contract: {counts['max_gold_spans']}")
    print(f"split evaluation contracts: {split['eval']}")
    print(f"split development contracts: {split['dev']}")
    print(f"split overlap: {split['overlap']}")


def _verify_data(args: argparse.Namespace) -> int:
    try:
        path = download_cuad(args.cache_dir, args.revision)
        dataset = load_cuad(path)
        validate_dataset(dataset)
        split = load_split(args.split)
        validate_split(split, dataset)
        report = write_data_report(args.report, dataset, split, [])
    except DatasetError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    _print_verify_summary(report)
    print(f"report: {args.report}")
    return 0


def _resolve_config(stub: bool, prompt_version: str, pricing: str) -> RuntimeConfig:
    if stub:
        model_id = read_model_id() or "stub"
        region = "us-east-1"
        return RuntimeConfig(
            model_id=model_id,
            region=region,
            dataset_revision=CUAD_REVISION,
            input_mode="plain_text",
            prompt_version=prompt_version,
            pricing_version=pricing,
        )
    return build_config(prompt_version, pricing)


def _run(args: argparse.Namespace) -> int:
    load_environment()
    configure_tracing()
    try:
        prompt = load_prompt()
        price_version = pricing_version()
        config = _resolve_config(args.stub, prompt.version, price_version)
    except (PromptError, PricingError, ConfigError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        path = download_cuad(args.data_dir / "cache")
        dataset = load_cuad(path)
    except DatasetError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    record = next((r for r in dataset.records if r.contract_id == args.contract_id), None)
    if record is None:
        print(f"error: unknown contract ID: {args.contract_id}", file=sys.stderr)
        return 2
    if not record.text.strip():
        print("error: contract text is empty", file=sys.stderr)
        return 2

    try:
        result = run_contract(
            record,
            config,
            run_id=args.run_id,
            runs_dir=args.runs_dir,
            stub=args.stub,
            prompt=prompt,
        )
    except RunExistsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "run_id": result.run_id,
                "run_dir": str(result.run_dir),
                "run_status": result.manifest["run_status"],
                "prediction_status": result.manifest["contracts"][0]["prediction_status"],
            }
        )
    )
    return result.exit_code


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "verify-data":
        return _verify_data(args)
    if args.command == "run":
        return _run(args)
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
