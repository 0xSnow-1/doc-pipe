# Tech Stack

## Runtime and tooling

- Python 3.12.
- uv for dependency management and command execution.
- The repository commits `uv.lock`.
- Ruff for linting and formatting.
- Pytest for unit and integration tests.
- Streamlit for the local prototype viewer.
- Pyright is recommended for schema and graph modules once the prototype stabilizes.
- Pyright is not a Phase 1 gate.

Required checks before merge:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Ruff selects `E`, `F`, `I`, `UP`, `B`, `SIM`, and `RUF`.
The line length is 100.

## Model

- Claude through AWS Bedrock.
- The exact model ID is pinned in configuration for each run.
- The model ID is recorded in the run manifest.
- AWS credentials come from the standard AWS credential chain.
- No secrets are stored in the repository.
- Phase 1 is synchronous and processes one contract at a time.
- There is no async framework and no concurrent model calls in Phase 1.

## Orchestration

- LangGraph `StateGraph` is the pipeline engine.
- The graph is deterministic: fixed nodes, fixed edges, no autonomous agent.
- Phase 1 graph: `load_text -> extract -> validate -> persist -> score -> END`.
- The graph uses the existing state in `src/states.py`.
- The existing state fields are `path`, `text`, `fields`, `errors`, and `retries`.
- `MessagesState` is not part of the Phase 1 contract.
- If message history is unused, replace `MessagesState` with a plain `TypedDict` to keep the state small.
- No autonomous planning, tool selection, or unbounded loops.
- No retry edge in the first prototype.
- The `retries` field stays at 0 until the evaluation shows retries solve a measured failure.
- A validation failure is recorded as `invalid_output` and counts as an error.
- Chunking is not used in the Phase 1 baseline.
- If a contract exceeds the model context window, the run records `context_overflow`.
- The pipeline does not silently truncate contract text.

The graph is an implementation detail.
The product behavior is still a fixed pipeline, not an agent.

## Schema and validation

Pydantic v2 is the source of truth for output shape and validation.
Phase 1 defines one clause type: `governing_law`.

The model returns `ModelClauseExtraction`.
The pipeline enriches it into `ClauseExtraction` after it derives the evidence span.

```python
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
        else:
            if self.value is not None or self.quote is not None:
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
```

Phase 1 uses `found` and `not_found` only.
The enum is extensible, but `ambiguous` is deferred until the evaluation shows a real need.

In Phase 1, `value` is the exact governing-law clause text.
`value` and `quote` may be identical.
The evaluation uses the quote span for matching.
There is no normalized jurisdiction field in Phase 1.
A normalized jurisdiction is a Phase 2 candidate only if a gold standard exists.

### Evidence span derivation

The model returns the quote, not character offsets.
The pipeline finds the quote in the source text and derives the span.

Rules:
- Find an exact substring match for `quote` in the source text.
- Require exactly one occurrence.
- Set `char_start` and `char_end` from that occurrence.
- Character spans are 0-based and half-open: `[char_start, char_end)`.
- The pipeline verifies that `source_text[char_start:char_end] == quote`.
- Zero matches produce `invalid_output` with reason `quote_not_found`.
- Multiple matches produce `invalid_output` with reason `quote_not_unique`.
- The pipeline never trusts model-provided offsets.

Spans refer to the exact text passed to the model.
For CUAD plain text, this is the CUAD contract text.

## Prompt assets

Prompts and clause definitions live in versioned files under `prompts/`.
Each prompt file has an explicit version.
The prompt contains:
- Instructions, including the not-found rule.
- The Pydantic schema and field descriptions.
- A plain-language definition of governing law.
- A few examples, including one absent example.
- The contract text inside explicit delimiters.

The prompt treats contract text as data, not instructions.
The prompt states that the model must not give legal advice.
No prompt text is hidden in application code.
The prompt version is recorded in every run manifest.

The model must return JSON matching `ModelClauseExtraction`.
No regex extraction of values from prose is allowed.
If JSON parsing fails, the result is `invalid_output`.

## Parsing

- Phase 1 input is the CUAD plain-text contract.
- Docling is deferred to Phase 2.
- The first baseline isolates extraction quality from parser quality.
- When Docling is added, parser fidelity is reported separately from extraction accuracy.
- CUAD character offsets are not reused against Docling text without explicit alignment.

## Storage

Phase 1 uses JSONL artifacts on disk.
There is no database in Phase 1.

Run layout:

```text
runs/<run_id>/
  manifest.json
  predictions.jsonl
  errors.jsonl
  scores.json
```

`manifest.json` records:
- `run_id`
- `timestamp_utc`
- `git_commit`
- `model_id`
- `prompt_version`
- `dataset_revision`
- `input_mode` (`plain_text` in Phase 1)
- `config_hash`
- `total_cost_usd`
- `total_latency_s`

`predictions.jsonl` contains one `ClauseExtraction` per contract.
`errors.jsonl` contains one row per error with the predicted value, gold value, quote, span, error type, and reason.
`scores.json` contains per-field precision, recall, F1, abstention accuracy, error counts by type, and cost and latency totals.

## Database schema

Phase 1 has no database.
The canonical record schema is the `ClauseExtraction` model above.
The on-disk schema is the JSONL layout above.
A DuckDB schema is intentionally deferred.
DuckDB enters only when querying JSONL artifacts becomes a demonstrated bottleneck.

## Evaluation

The evaluation harness is custom Python.
The baseline is recorded even when initial targets are missed.

Default match rule:
- A prediction matches a gold label when their character spans overlap.
- Any overlap counts as a match.
- Exact-match and overlap statistics are reported separately so the rule can be revisited.

Metrics:
- Per-field precision, recall, and F1.
- Abstention accuracy.
- Error counts by type.
- Cost and latency per contract.

Definitions:
- True positive: a found prediction whose derived span overlaps a gold span.
- False positive: a found prediction whose derived span does not overlap any gold span.
- False negative: a gold span with no overlapping found prediction.
- Precision: `TP / (TP + FP)`.
- Recall: `TP / (TP + FN)`.
- Abstention accuracy: correct not-found predictions divided by all contracts where the clause is absent.
- Wrong value: a found prediction on a contract with a gold span, but the predicted span does not overlap any gold span.
- Missed value: a `not_found` prediction on a contract with a gold span.
- Invented value: a found prediction on a contract with no gold span.
- Invalid output: schema validation, JSON parsing, or evidence verification failed.

## Observability

LangSmith is the tracing tool.
LangSmith traces the graph run, prompt construction, Bedrock call, validation, evidence derivation, persistence, and scoring.
Use a project name such as `doc-pipe-prototype`.
Tracing is enabled for live runs when `LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY` is set.
If the key is absent, the run still works and writes structured JSON logs.
Structured JSON logs are required for every run.
LangSmith is not part of the scoring path.
Tests must not call LangSmith.
No secrets are stored in the repository.

## Prototype frontend

Streamlit is the local prototype viewer.
It reads and writes the same JSONL artifacts as the CLI.
It does not add a backend, database, or duplicate scoring logic.

The viewer can:
- Select a CUAD contract.
- Run the pipeline for that contract.
- Show the contract text.
- Show the extracted clause, status, quote, and character span.
- Show the run metrics and error list.
- Browse previous runs.

The viewer is a local demo and inspection tool.
It is not a production UI.
It has no authentication, multi-user support, or cloud deployment.
It must state that outputs are not legal advice.

The CLI remains the source of truth for automated evaluation.
The viewer consumes the artifacts that the CLI and pipeline produce.

## CLI and delivery

Phase 1 exposes a local CLI and a local Streamlit viewer.
It does not include an API, production UI, container, or cloud deployment.

## Deferred tools

- Docling: deferred to Phase 2 so the first baseline isolates extraction quality.
- DuckDB: deferred until JSONL querying is a demonstrated bottleneck.
- FastAPI: deferred until a second consumer needs a service interface.
- Docker: deferred until local reproducibility is insufficient.
- LlamaIndex: no role. Retrieval and indexing are out of scope.
- Production UI, authentication, and multi-user access: deferred.
- Fine-tuning: out of scope for the MVP.

The prototype imports only packages used by the current phase.
Deferred packages may exist in `pyproject.toml`, but the Phase 1 path must not import them.

## Engineering constraints

- Every found value must have a quote and a character span that match the source text.
- The system must return `not_found` rather than guess.
- LangGraph is deterministic. No autonomous agent loops.
- No conditional edges in Phase 1.
- No application-level retries in Phase 1.
- No retrieval or vector index.
- No hidden prompt logic outside versioned prompt files.
- No secrets in the repository.
- LangSmith credentials come from environment variables.
- LangSmith tracing must not be required for tests or automated evaluation.
- The Streamlit viewer must use the same pipeline and JSONL artifacts as the CLI.
- The Streamlit viewer must not contain scoring logic.
- Every run must record model, prompt, dataset, and config versions.
- Model calls in the required test suite are mocked or recorded.
- Live Bedrock calls are manual smoke tests only.
- The per-contract model budget is 0.50 USD and 60 seconds.
- A contract that exceeds the budget is marked `budget_exceeded` and reported.
- The evaluation baseline is recorded even if targets are missed.
