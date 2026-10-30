import pytest

from src.evidence import EvidenceError, build_extraction, derive_span
from src.schemas import ClauseStatus, ModelClauseExtraction


def test_one_match() -> None:
    text = "This agreement is governed by the laws of Delaware."
    quote = "governed by the laws of Delaware"
    start, end = derive_span(text, quote)
    assert text[start:end] == quote


def test_zero_matches() -> None:
    with pytest.raises(EvidenceError) as exc:
        derive_span("hello", "missing")
    assert exc.value.reason == "quote_not_found"


def test_two_non_overlapping_matches() -> None:
    with pytest.raises(EvidenceError) as exc:
        derive_span("abc abc", "abc")
    assert exc.value.reason == "quote_not_unique"


def test_two_overlapping_matches() -> None:
    with pytest.raises(EvidenceError) as exc:
        derive_span("aaa", "aa")
    assert exc.value.reason == "quote_not_unique"


def test_unicode() -> None:
    text = "Droit applicable: le droit francais. Fin."
    quote = "le droit francais"
    start, end = derive_span(text, quote)
    assert text[start:end] == quote


def test_newlines_and_tabs() -> None:
    text = "governed by\n\tthe laws of Delaware"
    quote = "governed by\n\tthe laws of Delaware"
    start, end = derive_span(text, quote)
    assert text[start:end] == quote


def test_full_contract_quote() -> None:
    text = "The laws of Delaware govern."
    start, end = derive_span(text, text)
    assert (start, end) == (0, len(text))


def test_blank_quote() -> None:
    with pytest.raises(EvidenceError) as exc:
        derive_span("text", "   ")
    assert exc.value.reason == "empty_quote"


def test_blank_value() -> None:
    model = ModelClauseExtraction(
        clause_type="governing_law",
        status=ClauseStatus.FOUND,
        value="  ",
        quote="text",
    )
    with pytest.raises(EvidenceError) as exc:
        build_extraction(model, "c", "text")
    assert exc.value.reason == "empty_value"


def test_build_extraction_found() -> None:
    text = "This agreement is governed by the laws of Delaware."
    model = ModelClauseExtraction(
        clause_type="governing_law",
        status=ClauseStatus.FOUND,
        value="governed by the laws of Delaware",
        quote="governed by the laws of Delaware",
    )
    extraction = build_extraction(model, "c", text)
    assert text[extraction.char_start : extraction.char_end] == extraction.quote


def test_build_extraction_not_found() -> None:
    model = ModelClauseExtraction(clause_type="governing_law", status=ClauseStatus.NOT_FOUND)
    extraction = build_extraction(model, "c", "text")
    assert extraction.char_start is None
    assert extraction.char_end is None
