from pathlib import Path

import pytest

from src.data import (
    ContractRecord,
    CuadDataset,
    DatasetError,
    Split,
    build_split,
    load_cuad,
    parse_cuad,
    validate_dataset,
    validate_split,
)
from src.schemas import GoldSpan

SMALL_COUNTS = {
    "contracts": 3,
    "clause_types": 1,
    "governing_law_entries": 3,
    "contracts_with_span": 2,
    "contracts_without_span": 1,
    "gold_spans": 2,
    "contracts_with_multiple_spans": 0,
    "max_gold_spans": 1,
}


def test_parse_small_fixture(small_dataset: CuadDataset) -> None:
    records = small_dataset.records
    assert [record.contract_id for record in records] == [
        "Positive Contract",
        "Negative Contract",
        "Repeated Contract",
    ]
    assert records[0].gold_spans[0].char_start == 24
    assert records[1].gold_spans == []


def test_counts(small_dataset: CuadDataset) -> None:
    assert small_dataset.counts() == SMALL_COUNTS


def test_validate_dataset_passes_with_expected_override(small_dataset: CuadDataset) -> None:
    assert validate_dataset(small_dataset, SMALL_COUNTS) == []


def test_validate_dataset_rejects_mismatch(small_dataset: CuadDataset) -> None:
    expected = dict(SMALL_COUNTS)
    expected["contracts"] = 511
    with pytest.raises(DatasetError, match="contracts"):
        validate_dataset(small_dataset, expected)


def test_duplicate_stripped_titles_are_rejected() -> None:
    dataset = CuadDataset(
        records=[
            ContractRecord(contract_id="Same", text="a"),
            ContractRecord(contract_id="Same", text="b"),
        ],
        clause_types=["q"],
        governing_law_entries=2,
    )
    expected = {
        "contracts": 2,
        "clause_types": 1,
        "governing_law_entries": 2,
        "contracts_with_span": 0,
        "contracts_without_span": 2,
        "gold_spans": 0,
        "contracts_with_multiple_spans": 0,
        "max_gold_spans": 0,
    }
    with pytest.raises(DatasetError, match="unique"):
        validate_dataset(dataset, expected)


def test_gold_span_past_end_is_rejected() -> None:
    dataset = CuadDataset(
        records=[
            ContractRecord(
                contract_id="c",
                text="short",
                gold_spans=[GoldSpan(char_start=2, char_end=100)],
            )
        ],
        clause_types=["q"],
        governing_law_entries=1,
    )
    expected = {
        "contracts": 1,
        "clause_types": 1,
        "governing_law_entries": 1,
        "contracts_with_span": 1,
        "contracts_without_span": 0,
        "gold_spans": 1,
        "contracts_with_multiple_spans": 0,
        "max_gold_spans": 1,
    }
    with pytest.raises(DatasetError, match="gold span"):
        validate_dataset(dataset, expected)


def _split_dataset() -> CuadDataset:
    positives = [
        ContractRecord(
            contract_id=f"pos-{i}", text="x", gold_spans=[GoldSpan(char_start=0, char_end=1)]
        )
        for i in range(12)
    ]
    negatives = [ContractRecord(contract_id=f"neg-{i}", text="x") for i in range(8)]
    return CuadDataset(records=positives + negatives, clause_types=["q"], governing_law_entries=12)


def test_build_split_is_deterministic() -> None:
    dataset = _split_dataset()
    assert build_split(dataset) == build_split(dataset)


def test_split_unknown_id_is_rejected(small_dataset: CuadDataset) -> None:
    split = Split(eval=["Positive Contract", "missing"], dev=[])
    with pytest.raises(DatasetError, match="unknown"):
        validate_split(split, small_dataset)


def test_split_overlap_is_rejected(small_dataset: CuadDataset) -> None:
    split = Split(eval=["Positive Contract"] * 10, dev=["Positive Contract"] * 10)
    with pytest.raises(DatasetError, match="overlap"):
        validate_split(split, small_dataset)


def test_parse_cuad_matches_load(tmp_path: Path, cuad_small_path: Path) -> None:
    assert parse_cuad(cuad_small_path) == load_cuad(cuad_small_path).records
