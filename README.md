# doc-pipe

Evidence-first contract clause extraction.

This prototype extracts one clause type, governing law, from CUAD commercial contracts.
Every found value must include an exact quote and a character span that matches the source text.
When the clause is absent, the system returns `not_found` and does not guess.

Outputs are not legal advice.
The system does not replace legal review.

## Status

Phase 0 bootstrap plus the governing-law live-extraction slice of Phase 1.
Scoring, the evaluation harness, and the Streamlit viewer are not part of this feature.

## Setup

```bash
uv sync
```

Python 3.12 and `uv` are required.

## Environment

Copy `.env.example` to `.env` or export the variables in your shell.
Never commit `.env`.

| Variable | Purpose |
| --- | --- |
| `BEDROCK_MODEL_ID` | Pinned Bedrock model ID for live runs |
| `BEDROCK_REGION` | Bedrock region, default `us-east-1` |
| `AWS_BEARER_TOKEN_BEDROCK` | Bedrock API key when not using the AWS credential chain |
| `LANGSMITH_TRACING` | Set to `true` to enable tracing |
| `LANGSMITH_API_KEY` | LangSmith API key |
| `LANGSMITH_PROJECT` | LangSmith project name |

Tracing is enabled only when `LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY` is set.
Tests never call Bedrock, Hugging Face, or LangSmith.

## Data

The pinned source is `CUAD_v1/CUAD_v1.json` from `theatticusproject/cuad` at revision `a3c393f5d103fd0c516374e4fdff676c8176dcb1`.

Verified facts for this revision:

| Fact | Value |
| --- | --- |
| Contracts | 510 |
| Clause types | 41 |
| Governing-law entries | 510 |
| Contracts with a governing-law span | 437 |
| Contracts with no governing-law span | 73 |
| Governing-law gold spans | 464 |
| Maximum gold spans on one contract | 4 |

The committed split is `data/split.json`.
It contains 10 evaluation contracts and 10 development contracts.
The evaluation set has 5 positive and 5 negative contracts.
The development set has 7 positive and 3 negative contracts.
The sets are disjoint.

## Commands

```bash
uv run doc-pipe verify-data
uv run doc-pipe run --contract-id "<id>" --stub
uv run doc-pipe run --contract-id "<id>"
```

`verify-data` downloads the pinned CUAD file through `huggingface_hub`, validates the counts and the split, and writes `data/data_report.json`.

`run --stub` performs no network call and writes a deterministic `not_found` prediction.
Use it for offline smoke checks.

A live `run` calls Claude Haiku 4.5 through AWS Bedrock.
It spends money and needs AWS credentials.

## Artifacts

Each run writes a folder under `runs/<run_id>/`:

```text
input.txt
manifest.json
predictions.jsonl
errors.jsonl
logs.jsonl
```

`manifest.json` records the run ID, model, prompt version and hash, dataset revision, config hash, pricing version, cost, latency, status, and per-contract usage.
`predictions.jsonl` contains one valid `ClauseExtraction` per contract.
`errors.jsonl` contains one error record per failure.
`logs.jsonl` contains one JSON object per event and never contains secrets or full contract text.

## Evidence rules

The model returns a quote, not character offsets.
The pipeline finds the quote by exact substring search.
The quote must appear exactly once.
The pipeline verifies that the source slice equals the quote.
Zero matches, multiple matches, blank evidence, and span mismatches produce an `invalid_output` error and no prediction row.

## Checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run pyright src
```

Ruff and pytest are merge gates.
Pyright is advisory.

## Non-goals

This feature does not include scoring, `scores.json`, the evaluation harness, the Streamlit viewer, batch runs, chunking, Docling, retries, conditional graph edges, a database, an HTTP API, authentication, or non-contract documents.
