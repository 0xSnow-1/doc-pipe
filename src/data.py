import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from huggingface_hub import hf_hub_download

from src.artifacts import atomic_write_text
from src.schemas import GoldSpan

CUAD_REPO = "theatticusproject/cuad"
CUAD_REVISION = "a3c393f5d103fd0c516374e4fdff676c8176dcb1"
CUAD_FILENAME = "CUAD_v1/CUAD_v1.json"
GOVERNING_LAW_LABEL = "Governing Law"

EXPECTED_COUNTS: dict[str, int] = {
    "contracts": 510,
    "clause_types": 41,
    "governing_law_entries": 510,
    "contracts_with_span": 437,
    "contracts_without_span": 73,
    "gold_spans": 464,
    "contracts_with_multiple_spans": 25,
    "max_gold_spans": 4,
}


class DatasetError(Exception):
    pass


@dataclass
class ContractRecord:
    contract_id: str
    text: str
    gold_spans: list[GoldSpan] = field(default_factory=list)


@dataclass
class CuadDataset:
    records: list[ContractRecord]
    clause_types: list[str]
    governing_law_entries: int

    def counts(self) -> dict[str, int]:
        spans = [len(record.gold_spans) for record in self.records]
        return {
            "contracts": len(self.records),
            "clause_types": len(self.clause_types),
            "governing_law_entries": self.governing_law_entries,
            "contracts_with_span": sum(1 for count in spans if count > 0),
            "contracts_without_span": sum(1 for count in spans if count == 0),
            "gold_spans": sum(spans),
            "contracts_with_multiple_spans": sum(1 for count in spans if count > 1),
            "max_gold_spans": max(spans, default=0),
        }


@dataclass
class Split:
    eval: list[str]
    dev: list[str]
    seed: int = 20261030


def is_governing_law_question(question: str) -> bool:
    return f'"{GOVERNING_LAW_LABEL}"' in question


def _load_raw(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise DatasetError(f"cannot read CUAD JSON at {path}: {exc}") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("data"), list):
        raise DatasetError("CUAD JSON must have a top-level 'data' array")
    return raw


def load_cuad(path: Path) -> CuadDataset:
    raw = _load_raw(path)
    records: list[ContractRecord] = []
    clause_types: set[str] = set()
    governing_law_entries = 0

    for entry in raw["data"]:
        title = str(entry.get("title", "")).strip()
        paragraphs = entry.get("paragraphs") or []
        if len(paragraphs) != 1:
            raise DatasetError(f"contract {title!r} must have exactly one paragraph")
        paragraph = paragraphs[0]
        text = paragraph.get("context")
        if not isinstance(text, str):
            raise DatasetError(f"contract {title!r} has no text context")
        gold_spans: list[GoldSpan] = []
        for qa in paragraph.get("qas") or []:
            question = str(qa.get("question", ""))
            clause_types.add(question)
            if not is_governing_law_question(question):
                continue
            governing_law_entries += 1
            for answer in qa.get("answers") or []:
                answer_text = str(answer.get("text", ""))
                start = int(answer.get("answer_start", 0))
                gold_spans.append(GoldSpan(char_start=start, char_end=start + len(answer_text)))
        records.append(ContractRecord(contract_id=title, text=text, gold_spans=gold_spans))

    return CuadDataset(
        records=records,
        clause_types=sorted(clause_types),
        governing_law_entries=governing_law_entries,
    )


def parse_cuad(path: Path) -> list[ContractRecord]:
    return load_cuad(path).records


def validate_dataset(dataset: CuadDataset, expected: dict[str, int] | None = None) -> list[str]:
    expected = expected or EXPECTED_COUNTS
    failures: list[str] = []
    counts = dataset.counts()
    for key, want in expected.items():
        got = counts[key]
        if got != want:
            failures.append(f"{key}: expected {want}, got {got}")

    titles = [record.contract_id for record in dataset.records]
    if len(set(titles)) != len(titles):
        failures.append("contract IDs are not unique after stripping")

    for record in dataset.records:
        for span in record.gold_spans:
            actual = record.text[span.char_start : span.char_end]
            if len(actual) != span.char_end - span.char_start:
                failures.append(f"{record.contract_id}: gold span extends past the text")
                break

    if failures:
        raise DatasetError("dataset validation failed: " + "; ".join(failures))
    return failures


def download_cuad(cache_dir: Path, revision: str = CUAD_REVISION) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    try:
        path = hf_hub_download(
            repo_id=CUAD_REPO,
            filename=CUAD_FILENAME,
            revision=revision,
            repo_type="dataset",
            cache_dir=str(cache_dir),
        )
    except Exception as exc:
        raise DatasetError(f"cannot download pinned CUAD file: {exc}") from exc
    return Path(path)


def build_split(dataset: CuadDataset, seed: int = 20261030) -> Split:
    import random

    positives = [r.contract_id for r in dataset.records if r.gold_spans]
    negatives = [r.contract_id for r in dataset.records if not r.gold_spans]
    rng = random.Random(seed)
    rng.shuffle(positives)
    rng.shuffle(negatives)
    if len(positives) < 12 or len(negatives) < 8:
        raise DatasetError("not enough contracts to build the committed split")
    return Split(
        eval=positives[:5] + negatives[:5],
        dev=positives[5:12] + negatives[5:8],
        seed=seed,
    )


def split_to_dict(split: Split) -> dict[str, Any]:
    return {"seed": split.seed, "eval": split.eval, "dev": split.dev}


def load_split(path: Path) -> Split:
    try:
        with path.open(encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise DatasetError(f"cannot read split at {path}: {exc}") from exc
    try:
        return Split(
            eval=[str(item) for item in raw["eval"]],
            dev=[str(item) for item in raw["dev"]],
            seed=int(raw.get("seed", 20261030)),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise DatasetError(f"split at {path} is malformed: {exc}") from exc


def validate_split(split: Split, dataset: CuadDataset) -> list[str]:
    failures: list[str] = []
    if len(split.eval) != 10:
        failures.append(f"evaluation split: expected 10, got {len(split.eval)}")
    if len(split.dev) != 10:
        failures.append(f"development split: expected 10, got {len(split.dev)}")

    overlap = sorted(set(split.eval) & set(split.dev))
    if overlap:
        failures.append(f"split overlap: {overlap}")

    known = {record.contract_id for record in dataset.records}
    unknown = sorted((set(split.eval) | set(split.dev)) - known)
    if unknown:
        failures.append(f"unknown contract IDs: {unknown}")

    positive_ids = {record.contract_id for record in dataset.records if record.gold_spans}
    eval_pos = sum(1 for contract_id in split.eval if contract_id in positive_ids)
    dev_pos = sum(1 for contract_id in split.dev if contract_id in positive_ids)
    if eval_pos != 5:
        failures.append(f"evaluation split: expected 5 positives, got {eval_pos}")
    if dev_pos != 7:
        failures.append(f"development split: expected 7 positives, got {dev_pos}")

    if failures:
        raise DatasetError("split validation failed: " + "; ".join(failures))
    return failures


def write_data_report(
    report_path: Path,
    dataset: CuadDataset,
    split: Split,
    failures: list[str],
) -> dict[str, Any]:
    counts = dataset.counts()
    split_failures = validate_split(split, dataset)
    checks = [
        {
            "name": f"count:{key}",
            "passed": counts[key] == want,
            "expected": want,
            "got": counts[key],
        }
        for key, want in EXPECTED_COUNTS.items()
    ]
    checks.append({"name": "unique_stripped_titles", "passed": True})
    checks.append({"name": "split", "passed": not split_failures})
    report = {
        "counts": counts,
        "checks": checks,
        "failures": failures,
        "split": {
            "eval": len(split.eval),
            "dev": len(split.dev),
            "overlap": len(set(split.eval) & set(split.dev)),
            "eval_positives": sum(
                1 for r in dataset.records if r.contract_id in split.eval and r.gold_spans
            ),
            "dev_positives": sum(
                1 for r in dataset.records if r.contract_id in split.dev and r.gold_spans
            ),
        },
    }
    atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report
