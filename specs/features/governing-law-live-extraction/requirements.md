# Governing-Law Live Extraction

## 1. Feature identity

| Field | Value |
| --- | --- |
| Feature | Governing-law live extraction |
| Folder | `specs/features/governing-law-live-extraction/` |
| Phase | Phase 0 bootstrap plus the live-extraction slice of Phase 1 |
| Date | 2026-10-30 |
| Status | Approved for execution |
| Owner | Lead Software Engineer |

## 2. Goal

Prove the evidence-first pipeline end to end for one clause type.
Given one CUAD contract, call Claude Haiku 4.5 through Bedrock, return a structured governing-law extraction, derive an exact quote span, and write auditable run artifacts.
This feature stops before scoring and before the Streamlit viewer.

## 3. Scope

### In scope

- Pinned CUAD revision and a reproducible data verification command.
- A committed 20-contract split: 10 evaluation and 10 development contracts.
- Pydantic v2 schemas for model output and enriched extraction.
- A versioned governing-law prompt file.
- A LangChain `ChatBedrock` model adapter using `with_structured_output(ModelClauseExtraction)`.
- Exact quote-to-span derivation with zero-match and multi-match rejection.
- A deterministic LangGraph pipeline: `load_text -> extract -> validate -> persist -> END`.
- JSONL run artifacts: `manifest.json`, `predictions.jsonl`, `errors.jsonl`, `logs.jsonl`, and `input.txt`.
- Structured JSON logs to the terminal and to the run folder.
- Optional LangSmith tracing through environment variables.
- Cost and latency capture using a pinned price table.
- Ruff, pytest, and advisory Pyright checks.

### Out of scope

- Precision, recall, abstention accuracy, and error scoring.
- `scores.json` and the evaluation harness.
- The Streamlit viewer.
- Multi-contract batch runs.
- Prompt iteration tooling.
- Chunking, Docling, retries, conditional graph edges, and agentic planning.
- Database, HTTP API, container, cloud deployment, authentication, and multi-user access.
- Non-contract document types, private contracts, and fine-tuning.
- A normalized jurisdiction field.
- The `ambiguous` status.

## 4. Locked decisions

| Decision | Choice |
| --- | --- |
| Scope | Phase 0 plus live extraction; no scoring or viewer |
| Code layout | Flat modules under `src/`; `src/` is the import package |
| CLI | `doc-pipe` console script with `verify-data` and `run` subcommands |
| Default mode | Live Bedrock call; `--stub` for offline tests and smoke checks |
| Data source | `CUAD_v1/CUAD_v1.json` from `theatticusproject/cuad` at revision `a3c393f5d103fd0c516374e4fdff676c8176dcb1` |
| Prompt format | Markdown body with TOML front matter and an explicit `version` |
| Model adapter | LangChain `ChatBedrock` plus `with_structured_output(ModelClauseExtraction)` |
| Invalid output | No prediction row; an error row in `errors.jsonl` |
| Logs | JSON lines to stderr and to `runs/<run_id>/logs.jsonl` |
| Split | Committed IDs generated with seed `20261030` |
| Cost | Pinned per-million-token price table in `config/pricing.toml` |
| Training/eval isolation | Evaluation and development contracts are disjoint |

## 5. Data contract

The pinned revision is `a3c393f5d103fd0c516374e4fdff676c8176dcb1`.
The source file is `CUAD_v1/CUAD_v1.json`.
The file is SQuAD-style JSON with a top-level `version` and a `data` array.

Verified facts for this revision:

| Fact | Value |
| --- | --- |
| Contracts | 510 |
| Clause types | 41 |
| Governing-law entries | 510 |
| Contracts with at least one governing-law span | 437 |
| Contracts with no governing-law span | 73 |
| Governing-law gold spans | 464 |
| Contracts with multiple gold spans | 25 |
| Maximum gold spans on one contract | 4 |
| Gold spans whose slice equals the answer text | 464 of 464 |

Rules:

- Each contract has exactly one paragraph with a `context` field.
- `contract_id` is the contract `title` with leading and trailing whitespace removed.
- Stripped titles are unique.
- The extractor receives only the contract text.
- Gold spans are loaded for audit and future scoring, but are never passed to the model or the prompt.
- Character offsets are Python string indices and are 0-based, half-open: `[char_start, char_end)`.

The committed split is `data/split.json`.
The split contains 10 evaluation contracts and 10 development contracts.
The evaluation set has 5 contracts with a governing-law span and 5 without.
The development set has 7 contracts with a governing-law span and 3 without.
The two sets are disjoint.
The exact IDs are listed in Appendix A.

## 6. Functional requirements

| ID | Requirement | Acceptance check |
| --- | --- | --- |
| FR-1 | The CLI exposes `doc-pipe verify-data` and `doc-pipe run`. | `uv run doc-pipe --help` lists both subcommands. |
| FR-2 | `verify-data` downloads the pinned CUAD JSON through `huggingface_hub` and caches it under `data/cache/`. | A clean cache downloads the file; a second run reads the cache. |
| FR-3 | `verify-data` validates the counts in Section 5 and rejects a mismatch. | A tampered fixture with 511 contracts fails with a clear error. |
| FR-4 | `verify-data` validates the split: 10 plus 10, disjoint, 5/5 evaluation mix, 7/3 development mix. | A split with an overlap fails. |
| FR-5 | `verify-data` writes `data/data_report.json` atomically and prints a human summary. | The report contains the counts, checks, and split status. |
| FR-6 | `run` accepts exactly one `--contract-id` and resolves it against the pinned dataset. | An unknown ID exits 2 before a run folder is created. |
| FR-7 | `run` calls Bedrock by default and uses the `BEDROCK_MODEL_ID` model. | A live run records the model ID in the manifest. |
| FR-8 | `run --stub` performs no network call and returns a deterministic `not_found` extraction. | Stub mode works with no AWS credentials and writes one `not_found` prediction. |
| FR-9 | The model call uses `with_structured_output(ModelClauseExtraction)`. | The adapter receives a `ModelClauseExtraction`, not raw prose. |
| FR-10 | A found extraction must include a non-empty `value` and a non-empty `quote`. | Pydantic rejects missing evidence. |
| FR-11 | A not-found extraction must not carry `value`, `quote`, or a span. | Pydantic rejects carried evidence. |
| FR-12 | The pipeline derives the span by exact substring search and requires exactly one occurrence. | One match produces a span; zero and multiple matches produce `invalid_output`. |
| FR-13 | The pipeline verifies `source_text[char_start:char_end] == quote`. | A mismatch produces `invalid_output` with reason `span_mismatch`. |
| FR-14 | Valid extractions are written to `predictions.jsonl` exactly once. | A stub run has one row; an invalid-output run has zero rows. |
| FR-15 | Every error is written to `errors.jsonl` with type, reason, prediction-side fields, and gold spans. | The error schema in Section 8 is satisfied. |
| FR-16 | `manifest.json` records the required run metadata and per-contract usage. | All fields in Section 8 are present and non-null where required. |
| FR-17 | `logs.jsonl` contains one JSON object per line and never contains secrets or full contract text. | The log test scans for the test secret and the contract text hash only. |
| FR-18 | LangSmith tracing is enabled only when `LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY` is set. | Tests run with tracing disabled and make no LangSmith calls. |
| FR-19 | Cost is computed from input and output tokens using `config/pricing.toml`. | The pricing test matches expected USD to 6 decimals. |
| FR-20 | The per-contract cost budget is 0.50 USD and the latency budget is 60 seconds. | A high-usage response or a timeout records `budget_exceeded`. |
| FR-21 | Context overflow is recorded as `context_overflow`; text is never silently truncated. | A fake `InputTooLong` response records the error and no prediction. |
| FR-22 | The graph has fixed nodes and fixed edges with no conditional edges and no retries. | The graph source contains one linear chain; `retries` stays 0. |
| FR-23 | The prompt is loaded only from `prompts/governing_law.md`; no prompt prose lives in Python. | A repository scan finds no governing-law instruction text outside the prompt file. |
| FR-24 | The prompt version and SHA-256 are recorded in the manifest. | The values match the prompt file used by the run. |

## 7. Schemas

The canonical schema follows the constitution.

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

Additional schemas:

```python
class GoldSpan(BaseModel):
    char_start: int
    char_end: int


class ErrorRecord(BaseModel):
    contract_id: str
    error_type: Literal[
        "invalid_output",
        "context_overflow",
        "budget_exceeded",
        "operational_error",
    ]
    reason: str
    detail: str | None = None
    predicted_value: str | None = None
    quote: str | None = None
    char_start: int | None = None
    char_end: int | None = None
    gold_spans: list[GoldSpan] = []
    model_id: str | None = None
    prompt_version: str
    created_at_utc: str
```

The graph state stays small and matches the constitution.

```python
from typing import Any, TypedDict


class ExtractionState(TypedDict, total=False):
    path: str
    text: str
    fields: dict[str, Any] | None
    errors: list[dict[str, Any]]
    retries: int
```

`MessagesState` is not used.

## 8. Artifacts

Run layout:

```text
runs/<run_id>/
  input.txt
  manifest.json
  predictions.jsonl
  errors.jsonl
  logs.jsonl
```

`manifest.json`:

```json
{
  "run_id": "20261030T173000Z-a1b2c3d4",
  "timestamp_utc": "2026-10-30T17:30:00Z",
  "git_commit": "abc123def456",
  "model_id": "global.anthropic.claude-haiku-4-5-20251001-v1:0",
  "prompt_version": "1.0.0",
  "prompt_sha256": "…",
  "dataset_revision": "a3c393f5d103fd0c516374e4fdff676c8176dcb1",
  "input_mode": "plain_text",
  "config_hash": "…",
  "pricing_version": "2026-10-30",
  "total_cost_usd": 0.012345,
  "total_latency_s": 4.21,
  "run_status": "completed",
  "contracts": [
    {
      "contract_id": "…",
      "prediction_status": "found",
      "input_tokens": 12000,
      "output_tokens": 80,
      "cost_usd": 0.0124,
      "latency_s": 4.21,
      "errors": []
    }
  ]
}
```

`predictions.jsonl` contains one `ClauseExtraction` per valid contract.
Invalid output does not create a prediction row.
`errors.jsonl` contains one `ErrorRecord` per error.
`logs.jsonl` contains one JSON object per log event.

Required manifest fields:

- `run_id`
- `timestamp_utc`
- `git_commit`
- `model_id`
- `prompt_version`
- `prompt_sha256`
- `dataset_revision`
- `input_mode`
- `config_hash`
- `pricing_version`
- `total_cost_usd`
- `total_latency_s`
- `run_status`
- `contracts`

## 9. Error handling

| Condition | Error type | Reason | Prediction row | Exit code |
| --- | --- | --- | --- | --- |
| Model returns invalid JSON or schema | `invalid_output` | `schema_error` or `json_error` | No | 0 |
| Model returns a quote absent from the text | `invalid_output` | `quote_not_found` | No | 0 |
| Model returns a quote appearing more than once | `invalid_output` | `quote_not_unique` | No | 0 |
| Span slice does not equal the quote | `invalid_output` | `span_mismatch` | No | 0 |
| Quote or value is blank after stripping | `invalid_output` | `empty_quote` or `empty_value` | No | 0 |
| Contract exceeds the model context window | `context_overflow` | `input_too_long` | No | 0 |
| Call exceeds 60 seconds | `budget_exceeded` | `timeout` | No if no result | 0 |
| Cost exceeds 0.50 USD | `budget_exceeded` | `cost` | Yes, if the prediction is valid | 0 |
| AWS authentication or network failure | `operational_error` | `auth`, `network`, `throttled`, or `unknown` | No | 1 |
| Empty contract text | `operational_error` | `empty_text` | No | 2 |
| Unknown contract ID | `operational_error` | `unknown_contract` | No | 2 |
| Missing live model configuration | `operational_error` | `missing_model_config` | No | 2 |
| Run folder already exists | `operational_error` | `run_exists` | No | 2 |

A valid prediction is never discarded because of a `budget_exceeded` warning.
No retry is attempted after any error.

## 10. Edge cases

| Edge case | Required behavior |
| --- | --- |
| Quote appears once | Derive the span and persist the prediction. |
| Quote appears zero times | `invalid_output` with `quote_not_found`. |
| Quote appears twice, non-overlapping | `invalid_output` with `quote_not_unique`. |
| Quote appears twice, overlapping | `invalid_output` with `quote_not_unique`. |
| Quote is the entire contract | Accepted if it appears exactly once and the slice matches. |
| Quote contains newlines or tabs | Exact match only; no whitespace normalization. |
| Quote contains Unicode | Python string indices are used; the slice must match. |
| Quote differs only by case | Exact match fails with `quote_not_found`. |
| Contract has no governing-law clause | The model returns `not_found`; no span is stored. |
| Model returns `not_found` with a value or quote | `invalid_output` with `schema_error`. |
| Model returns `found` with no quote | `invalid_output` with `schema_error`. |
| Contract text is empty | Rejected at the CLI boundary with exit 2. |
| Dataset revision returns different counts | `verify-data` fails with a mismatch report. |
| Split contains an unknown ID | `verify-data` fails. |
| Split has an overlap | `verify-data` fails. |
| Two contracts share a stripped title | Dataset validation fails. |
| Hugging Face is unreachable and cache is cold | Exit 1 with a clear download error. |
| Hugging Face is unreachable and cache is warm | The cached file is used. |
| AWS credentials are absent in live mode | Exit 1; a failed manifest and log are written when the run folder exists. |
| `--stub` is used without AWS credentials | The run succeeds. |
| LangSmith variables are absent | The run succeeds without tracing. |
| Prompt file is missing a required section | Startup fails before the model call. |
| Prompt contains an evaluation or development contract ID | The prompt test fails. |

## 11. CLI contract

```bash
uv run doc-pipe verify-data
uv run doc-pipe run --contract-id "<id>"
uv run doc-pipe run --contract-id "<id>" --stub
```

`verify-data` options:

- `--revision` overrides the pinned revision for explicit experiments.
- `--cache-dir` overrides `data/cache/`.
- `--report` overrides `data/data_report.json`.
- `--split` overrides `data/split.json`.

`run` options:

- `--contract-id` is required.
- `--stub` disables the network and uses the deterministic stub.
- `--run-id` overrides the generated run ID.
- `--runs-dir` overrides `runs/`.
- `--data-dir` overrides the dataset location.

Exit codes:

- `0`: the command completed and wrote its artifacts, including per-contract extraction errors.
- `1`: a data, download, authentication, or network failure prevented completion.
- `2`: invalid arguments, unknown contract, missing configuration, or an existing run folder.

## 12. Non-functional requirements

- Python 3.12 and `uv`.
- Ruff with `E`, `F`, `I`, `UP`, `B`, `SIM`, `RUF`; line length 100.
- Pytest for all automated tests.
- Pyright is advisory, not a merge gate.
- No secrets in the repository; `.env` is ignored.
- Tests never call Bedrock, Hugging Face, or LangSmith.
- Live calls are manual smoke tests only.
- Model calls are synchronous and process one contract at a time.
- All writes to run artifacts are atomic where a single file is replaced.
- No prompt text is hidden in application code.
- The system states that outputs are not legal advice in the README.

## 13. Strict non-requirements

This feature must not add:

- `scores.json`
- Precision, recall, F1, abstention accuracy, or error scoring
- `wrong_value`, `missed_value`, or `invented_value` classification
- The evaluation harness
- The Streamlit viewer
- Batch extraction
- Chunking
- Docling or PDF parsing
- Retries or conditional graph edges
- The `ambiguous` status
- A normalized jurisdiction field
- A database, DuckDB, HTTP API, FastAPI, Docker, or cloud deployment
- Authentication, multi-user access, or access control
- Non-contract documents
- Private or client contracts
- Fine-tuning or custom model training
- Retrieval, embeddings, or a vector index
- `MessagesState`

## 14. Acceptance criteria

The feature is accepted when all of these are true:

- `uv run ruff check .` passes.
- `uv run ruff format --check .` passes.
- `uv run pytest` passes on three consecutive runs.
- `uv run pyright src` reports no errors, or its findings are documented as advisory.
- `uv run doc-pipe verify-data` writes a report with 510 contracts, 41 clause types, 510 governing-law entries, 437 with answers, 73 without, and 464 gold spans.
- `uv run doc-pipe run --contract-id "<eval id>" --stub` writes a run folder with one `not_found` prediction and zero errors.
- A live run on one evaluation positive contract returns `found` or `not_found` and writes all artifacts.
- Every found prediction has a quote and a span, and the source slice equals the quote.
- A live run on one evaluation negative contract returns `not_found` without a span, or records an explicit error.
- Duplicate quotes, missing quotes, schema failures, context overflow, timeouts, and high cost each produce the specified error row in tests.
- The manifest contains every required field.
- `logs.jsonl` is valid JSONL and contains no secrets or full contract text.
- LangSmith tracing is absent when the environment variables are unset.
- The repository contains no committed `.env`, AWS key, or LangSmith key.

## Appendix A: Committed split IDs

Evaluation positives:

1. `GOOSEHEADINSURANCE,INC_04_02_2018-EX-10.6-Franchise Agreement`
2. `HOLIDAYRVSUPERSTORESINC_04_15_2002-EX-10.13-ENDORSEMENT AGREEMENT`
3. `SANDRIDGEENERGYINC_08_06_2009-EX-10.6-OPERATIONS AND MAINTENANCE AGREEMENT`
4. `BLUEHILLSBANCORP,INC_05_20_2014-EX-1.1-AGENCY AGREEMENT`
5. `MERCATAINC_03_09_2000-EX-10.21-SPONSORSHIP AGREEMENT`

Evaluation negatives:

1. `NETGEAR,INC_04_21_2003-EX-10.16- AMENDMENT #2 TO THE DISTRIBUTION AGREEMENT`
2. `ScansourceInc_20190822_10-K_EX-10.39_11793959_EX-10.39_Distributor Agreement`
3. `PhotronicsInc_20171219_10-QA_EX-10.28_10982650_EX-10.28_Outsourcing Agreement`
4. `ZtoExpressCaymanInc_20160930_F-1_EX-10.10_9752871_EX-10.10_Transportation Agreement`
5. `GluMobileInc_20070319_S-1A_EX-10.09_436630_EX-10.09_Content License Agreement3`

Development positives:

1. `XENCORINC_10_25_2013-EX-10.24-COLLABORATION AGREEMENT (3)`
2. `PhasebioPharmaceuticalsInc_20200330_10-K_EX-10.21_12086810_EX-10.21_Development Agreement`
3. `EuromediaHoldingsCorp_20070215_10SB12G_EX-10.B(01)_525118_EX-10.B(01)_Content License Agreement`
4. `BIOFRONTERAAG_04_29_2019-EX-4.17-SUPPLY AGREEMENT`
5. `QIWI_06_16_2017-EX-99.(D)(2)-COOPERATION AGREEMENT`
6. `SPARKLINGSPRINGWATERHOLDINGSLTD_07_03_2002-EX-10.13-SOFTWARE LICENSE AND MAINTENANCE AGREEMENT`
7. `ENTERPRISEPRODUCTSPARTNERSLP_07_08_1998-EX-10.3-TRANSPORTATION CONTRACT`

Development negatives:

1. `PfHospitalityGroupInc_20150923_10-12G_EX-10.1_9266710_EX-10.1_Franchise Agreement3`
2. `ADMA BioManufacturing, LLC -  Amendment #3 to Manufacturing Agreement`
3. `XLITECHNOLOGIES,INC_12_02_2015-EX-10.02-STRATEGIC ALLIANCE AGREEMENT`

Selection rule:
Positives are contracts with at least one governing-law span.
Negatives are contracts with none.
Each list is shuffled with `random.Random(20261030)`.
Evaluation takes the first 5 positives and first 5 negatives.
Development takes the next 7 positives and next 3 negatives.
All IDs are stripped of leading and trailing whitespace.

## Appendix B: Model and pricing

| Field | Value |
| --- | --- |
| Model ID | `global.anthropic.claude-haiku-4-5-20251001-v1:0` |
| Region | `us-east-1` |
| Context window | 200K tokens |
| Max output | 1024 tokens for this feature |
| Temperature | 0.0 |
| Global input price | 1.00 USD per million tokens |
| Global output price | 5.00 USD per million tokens |
| Regional input price | 1.10 USD per million tokens |
| Regional output price | 5.50 USD per million tokens |
| Per-contract cost budget | 0.50 USD |
| Per-contract latency budget | 60 seconds |

The price table is stored in `config/pricing.toml` with a `version` and `source` field.
The pinned model ID uses the global endpoint, so the global rates apply.
If the model ID changes to a regional endpoint, the price table must change in the same commit.
