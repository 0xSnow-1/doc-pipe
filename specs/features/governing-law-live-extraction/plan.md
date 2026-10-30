# Implementation Plan: Governing-Law Live Extraction

## How to use this plan

Work the groups in order.
Each group ends with a verifiable state.
Do not start a group until its dependencies pass.
Do not add scoring, the viewer, retries, chunking, or conditional graph edges.
Mark a task complete only after its verification command passes.

## Dependency graph

```text
Group 0
  -> Group 1
  -> Group 3
Group 1
  -> Group 2
  -> Group 4
Group 2 + Group 4
  -> Group 5
Group 1 + Group 2 + Group 5
  -> Group 6
Group 6
  -> Group 7
Group 7
  -> Group 8
Group 8
  -> Group 9
  -> Group 10
Group 9 + Group 10
  -> Group 11
```

## Group 0: Repository hygiene and dependency baseline

Depends on: nothing.

- [x] 0.1 Add `.gitignore` entries for `.env`, `.venv/`, `runs/`, `data/cache/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `.pyright/`, and `*.pyc`.
- [x] 0.2 Add a Hatchling build backend, `doc-pipe` console script, and wheel package config for `src/` in `pyproject.toml`.
- [x] 0.3 Add `langchain-aws`, `huggingface-hub`, and `python-dotenv` to runtime dependencies.
- [x] 0.4 Add `pyright` to the development dependency group.
- [x] 0.5 Remove the unused `huggingface` dependency.
- [x] 0.6 Add Ruff configuration for line length 100 and the required rule set.
- [x] 0.7 Add pytest configuration with `pythonpath = ["."]` and `testpaths = ["tests"]`.
- [x] 0.8 Add `src/__init__.py`.
- [x] 0.9 Remove the broken `main.py`; the console script is the only CLI entry point.
- [x] 0.10 Remove the empty `src/tools.py` unless a later group needs it.
- [x] 0.11 Run `uv sync` and confirm `uv run python -c "import src"` succeeds.

Exit check:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

## Group 1: Schemas and graph state

Depends on: Group 0.

- [x] 1.1 Create `src/schemas.py` with `ClauseStatus`, `ModelClauseExtraction`, `ClauseExtraction`, `GoldSpan`, and `ErrorRecord`.
- [x] 1.2 Replace `AgenticState` and `MessagesState` in `src/states.py` with the `ExtractionState` TypedDict.
- [x] 1.3 Add `tests/test_schemas.py` for every validator branch.
- [x] 1.4 Add `tests/test_state.py` to assert the state keys and the `retries` default.

Exit check:

```bash
uv run pytest tests/test_schemas.py tests/test_state.py
```

No module imports `MessagesState`.

## Group 2: Evidence span derivation

Depends on: Group 1.

- [x] 2.1 Create `src/evidence.py` with `EvidenceError`, `derive_span(text, quote)`, and `build_extraction(model_output, contract_id, text)`.
- [x] 2.2 Implement exact substring search.
- [x] 2.3 Count overlapping occurrences by searching again from `first + 1`.
- [x] 2.4 Reject zero matches with `quote_not_found`.
- [x] 2.5 Reject multiple matches with `quote_not_unique`.
- [x] 2.6 Verify `text[start:end] == quote` and reject with `span_mismatch`.
- [x] 2.7 Reject blank values and blank quotes.
- [x] 2.8 Add `tests/test_evidence.py` for one match, zero matches, two non-overlapping matches, two overlapping matches, Unicode, newlines, a full-contract quote, and a blank quote.

Exit check:

```bash
uv run pytest tests/test_evidence.py
```

A valid found extraction has a span whose slice equals the quote.

## Group 3: Data layer and committed split

Depends on: Group 0.

- [x] 3.1 Create `src/data.py` with the pinned repo, revision, file name, and expected counts.
- [x] 3.2 Implement `download_cuad(cache_dir, revision)` with `hf_hub_download`.
- [x] 3.3 Implement `parse_cuad(path)` into `ContractRecord` objects with `contract_id`, `text`, and `gold_spans`.
- [x] 3.4 Implement dataset validation for 510 contracts, 41 clause types, 510 governing-law entries, 437 with answers, 73 without, 464 spans, and all span slices matching the text.
- [x] 3.5 Implement split loading and validation for size, disjointness, and positive/negative counts.
- [x] 3.6 Add `scripts/build_split.py` with seed `20261030` and the rule in Appendix A of `requirements.md`.
- [x] 3.7 Generate and commit `data/split.json` with the exact IDs from Appendix A.
- [x] 3.8 Implement `data_report.json` generation.
- [x] 3.9 Add `tests/fixtures/cuad_small.json` with synthetic contracts: one positive, one negative, and one repeated-quote case.
- [x] 3.10 Add `tests/test_data.py` for parsing, count validation, split validation, unknown IDs, overlaps, duplicate stripped titles, and span-slice checks.
- [x] 3.11 Add `tests/test_split.py` for the committed split and the seed rule.

Exit check:

```bash
uv run pytest tests/test_data.py tests/test_split.py
```

The committed split is valid and disjoint.

## Group 4: Prompt assets

Depends on: Group 1.

- [x] 4.1 Create `prompts/governing_law.md` with TOML front matter: `version = "1.0.0"`, `clause_type = "governing_law"`, and `description`.
- [x] 4.2 Include the role, the governing-law definition, the not-found rule, the exact-quote rule, the no-legal-advice rule, and the treat-text-as-data rule.
- [x] 4.3 Include the `{{ schema_json }}` placeholder for the Pydantic schema.
- [x] 4.4 Include one synthetic found example and one synthetic absent example.
- [x] 4.5 Include the contract inside explicit `<contract>` and `</contract>` delimiters with a `{{ contract_text }}` placeholder.
- [x] 4.6 Create `src/prompts.py` with `PromptAsset`, TOML front-matter parsing using `tomllib`, placeholder validation, rendering, and SHA-256.
- [x] 4.7 Add `tests/test_prompts.py` for front matter, version, required sections, both placeholders, no evaluation or development IDs, and no prompt prose in Python.

Exit check:

```bash
uv run pytest tests/test_prompts.py
```

A rendered prompt contains the schema and the contract text.

## Group 5: Configuration, pricing, and model adapter

Depends on: Groups 1, 2, and 4.

- [x] 5.1 Create `config/pricing.toml` with the global and regional Haiku 4.5 rates, a version, and a source.
- [x] 5.2 Create `src/config.py` with `RuntimeConfig`, `.env` loading through `python-dotenv`, environment validation, and a deterministic `config_hash`.
- [x] 5.3 Create `src/pricing.py` with `compute_cost(model_id, input_tokens, output_tokens)`.
- [x] 5.4 Create `src/llm.py` with `ExtractionResult`, an `Extractor` protocol, `LangChainExtractor`, and `StubExtractor`.
- [x] 5.5 Build `ChatBedrock` with the pinned model, region, temperature 0.0, max output 1024, and a boto3 client with a 60-second read timeout and zero retries.
- [x] 5.6 Call `with_structured_output(ModelClauseExtraction)`.
- [x] 5.7 Extract input and output tokens from the response metadata.
- [x] 5.8 Map schema and JSON failures to `invalid_output`, context overflow to `context_overflow`, timeouts to `budget_exceeded`, and auth or network failures to `operational_error`.
- [x] 5.9 Add `tests/test_config.py`, `tests/test_pricing.py`, and `tests/test_llm.py` using a fake model and never a real Bedrock client.
- [x] 5.10 Test missing usage metadata, high usage, timeout, context overflow, auth failure, and a missing model ID.

Exit check:

```bash
uv run pytest tests/test_config.py tests/test_pricing.py tests/test_llm.py
```

No test reads AWS credentials or makes a network call.

## Group 6: Graph pipeline

Depends on: Groups 1, 2, and 5.

- [x] 6.1 Rewrite `src/graph.py` with `load_text`, `extract`, `validate`, and `persist` nodes.
- [x] 6.2 Wire the fixed edges `load_text -> extract -> validate -> persist -> END`.
- [x] 6.3 Keep `retries` at 0 and add no conditional edges.
- [x] 6.4 Make `extract` leave `fields=None` and append an `ErrorRecord` on failure.
- [x] 6.5 Make `validate` enrich a found extraction with a span and reject invalid evidence.
- [x] 6.6 Make `persist` write valid `ClauseExtraction` rows to `predictions.jsonl` and every error to `errors.jsonl`.
- [x] 6.7 Add `tests/test_graph.py` with fake extractors for found, not_found, duplicate quote, missing quote, and schema failure.
- [x] 6.8 Assert the graph source contains no conditional edges and no retry loop.

Exit check:

```bash
uv run pytest tests/test_graph.py
```

The persisted rows match the expected statuses.

## Group 7: Persistence, manifest, logging, and tracing

Depends on: Group 6.

- [x] 7.1 Create `src/artifacts.py` for run directory creation, `input.txt`, JSONL writers, atomic manifest writes, run-ID generation, and git commit lookup.
- [x] 7.2 Reject an existing run folder unless the caller chooses a new run ID.
- [x] 7.3 Create `src/logging.py` with a JSON-lines formatter, a stderr handler, a `logs.jsonl` handler, and redaction of secret-bearing fields.
- [x] 7.4 Create `src/tracing.py` with environment-gated LangSmith configuration and a no-op path.
- [x] 7.5 Create `src/runner.py` to orchestrate one run: create the folder, write the input, configure logging and tracing, invoke the graph, and finalize the manifest with cost and latency.
- [x] 7.6 Ensure the manifest is written even when an operational error aborts the model call.
- [x] 7.7 Add `tests/test_artifacts.py`, `tests/test_logging.py`, and `tests/test_tracing.py`.
- [x] 7.8 Test valid JSONL, required manifest fields, run-ID collisions, atomic replacement, secret redaction, and tracing disabled.

Exit check:

```bash
uv run pytest tests/test_artifacts.py tests/test_logging.py tests/test_tracing.py
```

## Group 8: CLI and packaging

Depends on: Group 7.

- [x] 8.1 Create `src/cli.py` with an argparse root command and the `verify-data` and `run` subcommands.
- [x] 8.2 Load `.env` and configure tracing before importing the pipeline.
- [x] 8.3 Implement the exit codes from `requirements.md`.
- [x] 8.4 Print machine results to stdout and structured JSON logs to stderr.
- [x] 8.5 Wire the `doc-pipe` console script in `pyproject.toml`.
- [x] 8.6 Add `tests/test_cli.py` for help output, missing arguments, `verify-data` with a mocked download, `run --stub` with temporary directories, and an existing run folder.
- [x] 8.7 Run `uv run doc-pipe --help` and `uv run doc-pipe run --help`.

Exit check:

```bash
uv run pytest tests/test_cli.py
uv run doc-pipe --help
```

## Group 9: Test suite completion and fixtures

Depends on: Group 8.

- [x] 9.1 Finish the synthetic CUAD fixture with a positive, a negative, and a repeated-quote contract.
- [x] 9.2 Finish the fake extractor fixtures for found, not_found, invalid schema, duplicate quote, missing quote, timeout, context overflow, and auth failure.
- [x] 9.3 Add an end-to-end stub integration test that asserts all five run files.
- [x] 9.4 Add a test that every found prediction slice equals its quote.
- [x] 9.5 Add a test that `errors.jsonl` is empty when there are no errors and contains one row per error otherwise.
- [x] 9.6 Add a test that no test performs network access.
- [x] 9.7 Run `uv run pytest` three times and confirm no flakes.

Exit check:

```bash
uv run pytest
uv run pytest
uv run pytest
```

## Group 10: Documentation

Depends on: Group 8.

- [x] 10.1 Update `README.md` with setup, environment variables, commands, artifacts, and non-goals.
- [x] 10.2 State that outputs are not legal advice.
- [x] 10.3 Document the pinned CUAD revision and the data facts.
- [x] 10.4 Document the live smoke test and the `--stub` mode.
- [x] 10.5 Confirm `.env` is not tracked and no secret appears in the README.

Exit check:

```bash
git status --short
```

No `.env`, key, or token is staged.

## Group 11: Live smoke test and sign-off

Depends on: Groups 9 and 10.

- [x] 11.1 Run `uv run doc-pipe verify-data` against the real pinned dataset.
- [x] 11.2 Run one live evaluation-positive contract.
- [x] 11.3 Run one live evaluation-negative contract.
- [x] 11.4 Inspect `manifest.json`, `predictions.jsonl`, `errors.jsonl`, and `logs.jsonl`.
- [x] 11.5 Verify every found span slice equals its quote.
- [x] 11.6 Confirm per-contract cost is at most 0.50 USD and latency is at most 60 seconds.
- [ ] 11.7 Optional: enable LangSmith and confirm one trace appears.
- [x] 11.8 Record the results in `verification.md`.
- [x] 11.9 Run the final gate: `uv run ruff check .`, `uv run ruff format --check .`, and `uv run pytest`.

Exit check:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

All manual checks in `verification.md` are marked pass, fail, or blocked with evidence.
