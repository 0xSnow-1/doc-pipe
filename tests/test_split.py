import json
from pathlib import Path

from src.data import ContractRecord, CuadDataset, Split, build_split, load_split, validate_split
from src.schemas import GoldSpan

ROOT = Path(__file__).resolve().parents[1]


def _dataset_for_committed_split(split: Split) -> CuadDataset:
    records: list[ContractRecord] = []
    for index, contract_id in enumerate(split.eval):
        spans = [GoldSpan(char_start=0, char_end=1)] if index < 5 else []
        records.append(ContractRecord(contract_id=contract_id, text="x", gold_spans=spans))
    for index, contract_id in enumerate(split.dev):
        spans = [GoldSpan(char_start=0, char_end=1)] if index < 7 else []
        records.append(ContractRecord(contract_id=contract_id, text="x", gold_spans=spans))
    return CuadDataset(records=records, clause_types=["q"], governing_law_entries=12)


def test_committed_split_shape() -> None:
    split = load_split(ROOT / "data" / "split.json")
    assert len(split.eval) == 10
    assert len(split.dev) == 10
    assert set(split.eval).isdisjoint(split.dev)
    validate_split(split, _dataset_for_committed_split(split))


def test_committed_split_has_expected_mix() -> None:
    split = load_split(ROOT / "data" / "split.json")
    dataset = _dataset_for_committed_split(split)
    positives = {record.contract_id for record in dataset.records if record.gold_spans}
    assert sum(1 for contract_id in split.eval if contract_id in positives) == 5
    assert sum(1 for contract_id in split.dev if contract_id in positives) == 7


def test_build_split_seed_rule() -> None:
    import random

    positives = [
        ContractRecord(
            contract_id=f"pos-{i}",
            text="x",
            gold_spans=[GoldSpan(char_start=0, char_end=1)],
        )
        for i in range(12)
    ]
    negatives = [ContractRecord(contract_id=f"neg-{i}", text="x") for i in range(8)]
    dataset = CuadDataset(
        records=positives + negatives,
        clause_types=["q"],
        governing_law_entries=12,
    )
    split = build_split(dataset, seed=20261030)

    pos_ids = [record.contract_id for record in positives]
    neg_ids = [record.contract_id for record in negatives]
    rng = random.Random(20261030)
    rng.shuffle(pos_ids)
    rng.shuffle(neg_ids)
    assert split.eval == pos_ids[:5] + neg_ids[:5]
    assert split.dev == pos_ids[5:12] + neg_ids[5:8]


def test_committed_split_is_valid_json() -> None:
    raw = json.loads((ROOT / "data" / "split.json").read_text())
    assert raw["seed"] == 20261030
    assert len(raw["eval"]) == 10
    assert len(raw["dev"]) == 10
