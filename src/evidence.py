from src.schemas import ClauseExtraction, ClauseStatus, ModelClauseExtraction


class EvidenceError(Exception):
    def __init__(self, reason: str, detail: str | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def derive_span(text: str, quote: str) -> tuple[int, int]:
    if not quote or not quote.strip():
        raise EvidenceError("empty_quote", "quote is blank after stripping")

    first = text.find(quote)
    if first == -1:
        raise EvidenceError("quote_not_found", "quote does not appear in the contract text")

    if text.find(quote, first + 1) != -1:
        raise EvidenceError("quote_not_unique", "quote appears more than once in the contract text")

    start = first
    end = first + len(quote)
    if text[start:end] != quote:
        raise EvidenceError("span_mismatch", "derived span does not slice back to the quote")
    return start, end


def build_extraction(
    model_output: ModelClauseExtraction,
    contract_id: str,
    text: str,
) -> ClauseExtraction:
    if model_output.status is ClauseStatus.NOT_FOUND:
        return ClauseExtraction(
            contract_id=contract_id,
            clause_type=model_output.clause_type,
            status=model_output.status,
        )

    value = model_output.value
    quote = model_output.quote
    if value is None or not value.strip():
        raise EvidenceError("empty_value", "value is blank after stripping")
    if quote is None or not quote.strip():
        raise EvidenceError("empty_quote", "quote is blank after stripping")

    start, end = derive_span(text, quote)
    return ClauseExtraction(
        contract_id=contract_id,
        clause_type=model_output.clause_type,
        status=model_output.status,
        value=value,
        quote=quote,
        char_start=start,
        char_end=end,
    )
