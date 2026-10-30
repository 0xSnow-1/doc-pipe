# Verification Scorecard: Governing-Law Live Extraction

## 1. Purpose

This document defines how the feature is proven.
It covers automated tests, type checks, data checks, run-artifact checks, log traces, and manual live checks.
A check is complete only when its evidence is recorded.
Status values are `pass`, `fail`, `blocked`, or `not-run`.

## 2. Environment

| Item | Requirement |
| --- | --- |
| Python | 3.12 |
| Package manager | `uv` |
| Test runner | `pytest` |
| Linter and formatter | Ruff |
| Type checker | Pyright, advisory |
| Network for automated tests | None |
| AWS credentials for automated tests | None |
| LangSmith for automated tests | Disabled |
| Live smoke test | AWS Bedrock credentials and network |

The project is Python only.
There is no Jest suite.
There is no HTTP API in this feature.
The only network check outside the live model call is a Hugging Face `curl` check.

## 3. Required merge gates

Run these from the project root.

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

All three must pass.
A failure blocks merge.

## 4. Advisory checks

```bash
uv run pyright src
```

Pyright is advisory and is not a Phase 1 gate.
Record the output in the scorecard.
Also run a syntax compilation check:

```bash
uv run python -m compileall -q src
```

## 5. Automated test matrix

| Test file | Cases | Expected evidence |
| --- | --- | --- |
| `tests/test_schemas.py` | Found with value and quote; found missing value; found missing quote; not_found with value; not_found with quote; found without span; span end equal to start; not_found with span | Every invalid case raises `ValidationError`; valid cases round-trip through `model_dump`. |
| `tests/test_state.py` | State keys; default retries; no `MessagesState` import | The state contains only `path`, `text`, `fields`, `errors`, and `retries`. |
| `tests/test_evidence.py` | One match; zero matches; two non-overlapping matches; two overlapping matches; Unicode; newlines; full-contract quote; blank quote; blank value | Found spans slice back to the quote; invalid cases raise `EvidenceError` with the expected reason. |
| `tests/test_data.py` | Parse synthetic CUAD fixture; count validation; duplicate stripped titles; split unknown ID; split overlap; gold span slice check | The parser returns stable contract IDs, text, and gold spans; invalid data raises a clear error. |
| `tests/test_split.py` | Ten evaluation and ten development IDs; disjoint sets; 5/5 and 7/3 mix; seed rule | The committed `data/split.json` passes and matches the rule. |
| `tests/test_prompts.py` | Front matter version; required sections; schema placeholder; contract placeholder; leakage scan | The prompt renders; no evaluation or development ID appears; no governing-law instructions exist in Python. |
| `tests/test_config.py` | `.env` load without overriding real environment; missing model ID; config hash determinism | Live mode fails fast without a model ID; the hash is stable across two builds. |
| `tests/test_pricing.py` | Input-only, output-only, mixed, unknown model | USD values match the pinned table to 6 decimals; an unknown model raises a clear error. |
| `tests/test_llm.py` | Fake found response; fake not_found response; schema error; missing usage; high usage; timeout; context overflow; auth failure | Each path returns the expected `ExtractionResult` error type and reason; no network call occurs. |
| `tests/test_graph.py` | Found; not_found; duplicate quote; missing quote; schema failure | The graph writes the expected prediction and error rows; no conditional edge is used. |
| `tests/test_artifacts.py` | Run folder creation; existing folder rejection; atomic manifest write; JSONL append; run-ID format; git commit lookup | Files exist with the expected names; an existing folder exits with a collision error. |
| `tests/test_logging.py` | JSONL format; required events; secret redaction; no full contract text | Every line parses as JSON; a planted secret and the contract text do not appear. |
| `tests/test_tracing.py` | Env unset; env set without key; env set with key | Tracing is off in the first two cases and on in the third; tests make no LangSmith call. |
| `tests/test_cli.py` | Help; missing contract ID; unknown contract; `verify-data` with mocked download; `run --stub`; existing run folder; exit codes | The command prints the expected summary, creates the expected files, and returns the documented exit code. |
| `tests/test_integration.py` | Stub run end to end | All five run files exist; one `not_found` prediction; zero error rows; every found slice check passes. |

## 6. Pytest fixtures

Required fixtures:

| Fixture | Purpose |
| --- | --- |
| `cuad_small` | Synthetic CUAD JSON with one positive contract, one negative contract, and one repeated-quote contract. |
| `contract_positive` | A contract whose text contains one exact governing-law quote. |
| `contract_negative` | A contract whose text contains no governing-law quote. |
| `contract_repeated_quote` | A contract whose quote appears twice. |
| `fake_found` | A fake extractor returning a valid found `ModelClauseExtraction`. |
| `fake_not_found` | A fake extractor returning a valid not-found extraction. |
| `fake_invalid_schema` | A fake extractor raising a schema validation error. |
| `fake_duplicate_quote` | A fake extractor returning a quote that appears twice. |
| `fake_missing_quote` | A fake extractor returning a quote that does not appear. |
| `fake_timeout` | A fake extractor raising a read timeout. |
| `fake_context_overflow` | A fake extractor raising an input-too-long error. |
| `fake_auth_error` | A fake extractor raising an authentication error. |
| `temp_runs_dir` | A temporary run root. |
| `temp_data_dir` | A temporary data root with the synthetic CUAD file and split. |
| `no_langsmith` | Clears LangSmith variables and asserts tracing stays off. |

Fixtures must not read real AWS credentials, call Hugging Face, or call LangSmith.

## 7. Data integrity checks

### 7.1 Pinned file reachability

```bash
curl -sI "https://huggingface.co/datasets/theatticusproject/cuad/resolve/a3c393f5d103fd0c516374e4fdff676c8176dcb1/CUAD_v1/CUAD_v1.json"
```

Expected: an HTTP 200 or 302 response.
Record the final status code.

### 7.2 Verify command

```bash
uv run doc-pipe verify-data
```

Expected human summary:

| Count | Expected |
| --- | --- |
| Contracts | 510 |
| Clause types | 41 |
| Governing-law entries | 510 |
| Contracts with a governing-law span | 437 |
| Contracts with no governing-law span | 73 |
| Governing-law gold spans | 464 |
| Maximum gold spans on one contract | 4 |
| Split evaluation contracts | 10 |
| Split development contracts | 10 |
| Split overlap | 0 |

Expected report: `data/data_report.json` exists and contains the same counts plus `checks` entries with `passed: true`.

### 7.3 Split check

```bash
uv run python -c "import json; d=json.load(open('data/split.json')); print(len(d['eval']), len(d['dev']))"
```

Expected: `10 10`.
The evaluation set contains 5 positive and 5 negative contracts.
The development set contains 7 positive and 3 negative contracts.
No contract appears in both sets.

## 8. Run artifact checks

### 8.1 Stub run

```bash
uv run doc-pipe run --contract-id "GOOSEHEADINSURANCE,INC_04_02_2018-EX-10.6-Franchise Agreement" --stub --runs-dir /tmp/doc-pipe-runs
```

Expected:

- `manifest.json`, `predictions.jsonl`, `errors.jsonl`, `logs.jsonl`, and `input.txt` exist.
- `predictions.jsonl` has one row with `status: "not_found"` and `char_start: null`.
- `errors.jsonl` is empty.
- `manifest.json` has every required field.
- The exit code is 0.

### 8.2 Manifest field check

```bash
uv run python - <<'PY'
import json, pathlib
run = sorted(pathlib.Path('/tmp/doc-pipe-runs').iterdir())[-1]
m = json.load(open(run / 'manifest.json'))
required = [
    'run_id', 'timestamp_utc', 'git_commit', 'model_id', 'prompt_version',
    'prompt_sha256', 'dataset_revision', 'input_mode', 'config_hash',
    'pricing_version', 'total_cost_usd', 'total_latency_s', 'run_status', 'contracts',
]
missing = [k for k in required if k not in m]
print('missing', missing)
print('contracts', m['contracts'])
PY
```

Expected: `missing []`.

### 8.3 JSONL validity

```bash
uv run python - <<'PY'
import json, pathlib
run = sorted(pathlib.Path('/tmp/doc-pipe-runs').iterdir())[-1]
for name in ('predictions.jsonl', 'errors.jsonl', 'logs.jsonl'):
    for i, line in enumerate(open(run / name), 1):
        if line.strip():
            json.loads(line)
    print(name, 'ok')
PY
```

Expected: all three files print `ok`.

### 8.4 Found-span check

For every prediction with `status == "found"`, assert:

```python
text[char_start:char_end] == quote
```

The check reads the matching `input.txt` or the CUAD contract text.
Any mismatch is a fail.

## 9. Error injection matrix

| Injection | Expected artifact | Expected exit code |
| --- | --- | --- |
| Fake schema error | `errors.jsonl` with `invalid_output` and `schema_error`; no prediction row | 0 |
| Fake JSON error | `errors.jsonl` with `invalid_output` and `json_error`; no prediction row | 0 |
| Quote appears zero times | `errors.jsonl` with `invalid_output` and `quote_not_found` | 0 |
| Quote appears twice | `errors.jsonl` with `invalid_output` and `quote_not_unique` | 0 |
| Span slice mismatch | `errors.jsonl` with `invalid_output` and `span_mismatch` | 0 |
| Blank quote | `errors.jsonl` with `invalid_output` and `empty_quote` | 0 |
| Context overflow | `errors.jsonl` with `context_overflow` and `input_too_long`; no prediction row | 0 |
| Timeout | `errors.jsonl` with `budget_exceeded` and `timeout`; no prediction row if no result | 0 |
| High cost | Prediction kept; `errors.jsonl` with `budget_exceeded` and `cost` | 0 |
| Authentication failure | `manifest.json` with `run_status: failed`; `errors.jsonl` with `operational_error` and `auth` | 1 |
| Network failure | `manifest.json` with `run_status: failed`; `errors.jsonl` with `operational_error` and `network` | 1 |
| Unknown contract | No run folder; clear message | 2 |
| Empty contract text | No run folder; clear message | 2 |
| Missing model ID in live mode | No run folder; clear message | 2 |
| Existing run folder | New run rejected; existing folder untouched | 2 |

## 10. Log and tracing checks

### 10.1 Log events

Expected `logs.jsonl` events for a normal run:

- `run_start`
- `contract_loaded`
- `prompt_rendered`
- `model_request`
- `model_response`
- `evidence_derived` or `validation_failed`
- `artifacts_written`
- `run_end`

Each line is a JSON object.
Each line includes `timestamp_utc`, `level`, `event`, `run_id`, and a message.
Contract and model events include `contract_id`.

### 10.2 Secret and leakage scan

```bash
uv run python - <<'PY'
import pathlib
run = sorted(pathlib.Path('/tmp/doc-pipe-runs').iterdir())[-1]
blob = (run / 'logs.jsonl').read_text()
for needle in ('AWS_BEARER_TOKEN_BEDROCK', 'LANGSMITH_API_KEY', 'BEDROCK_MODEL_ID='):
    print(needle, needle in blob)
PY
```

Expected: all three print `False`.

The test suite also plants a fake secret in the environment and asserts it never appears in the logs.

### 10.3 Tracing off

With `LANGSMITH_TRACING=false` and no key:

```bash
env -u LANGSMITH_API_KEY LANGSMITH_TRACING=false uv run doc-pipe run --contract-id "GOOSEHEADINSURANCE,INC_04_02_2018-EX-10.6-Franchise Agreement" --stub --runs-dir /tmp/doc-pipe-runs-tracing-off
```

Expected: the run succeeds and no LangSmith trace is created.

### 10.4 Tracing on, manual only

With `LANGSMITH_TRACING=true` and `LANGSMITH_API_KEY` set, run one live contract.
Expected: one trace appears in the configured LangSmith project.
This check is manual and is not part of the required test suite.

## 11. Live smoke test

This check is manual.
It uses real AWS credentials and spends money.

### 11.1 Verify data

```bash
uv run doc-pipe verify-data
```

Expected: the counts in Section 7.2.

### 11.2 Evaluation positive

```bash
uv run doc-pipe run --contract-id "GOOSEHEADINSURANCE,INC_04_02_2018-EX-10.6-Franchise Agreement"
```

Expected:

- The run completes with exit code 0.
- `predictions.jsonl` has one row.
- If the row is `found`, the quote is non-empty and `text[char_start:char_end] == quote`.
- If the row is `not_found`, no span is present.
- `manifest.json` records the model ID, prompt version, dataset revision, cost, and latency.
- Per-contract cost is at most 0.50 USD.
- Per-contract latency is at most 60 seconds.

### 11.3 Evaluation negative

```bash
uv run doc-pipe run --contract-id "NETGEAR,INC_04_21_2003-EX-10.16- AMENDMENT #2 TO THE DISTRIBUTION AGREEMENT"
```

Expected:

- The run completes with exit code 0.
- The prediction is `not_found` with no span, or an explicit error is recorded.
- No invented span is stored.

### 11.4 Record evidence

For each live run, record:

- Run ID.
- Contract ID.
- Prediction status.
- Quote and span, if found.
- Cost and latency.
- Error type and reason, if any.
- The exact command used.

## 12. No-API note

This feature has no HTTP API.
There are no endpoint curl checks.
The CLI is the runtime interface.
The only `curl` check is the pinned Hugging Face file reachability check in Section 7.1.

## 13. Scorecard

Mark each row after execution.
Attach evidence as a command output, file path, or short note.

| ID | Area | Check | Gate | Status | Evidence |
| --- | --- | --- | --- | --- | --- |
| V-01 | Static | `uv run ruff check .` | Required | pass | All checks passed. |
| V-02 | Static | `uv run ruff format --check .` | Required | pass | 34 files already formatted. |
| V-03 | Static | `uv run python -m compileall -q src` | Required | pass | Exit 0. |
| V-04 | Types | `uv run pyright src` | Advisory | pass | 0 errors, 0 warnings. |
| V-05 | Tests | `uv run pytest` | Required | pass | 102 passed. |
| V-06 | Tests | `uv run pytest` three consecutive runs | Required | pass | 102 passed on all three runs. |
| V-07 | Data | Pinned CUAD file returns HTTP 200 or 302 | Required | pass | HTTP 302. |
| V-08 | Data | `uv run doc-pipe verify-data` counts match | Required | pass | 510/41/510/437/73/464/4. |
| V-09 | Data | `data/data_report.json` checks all pass | Required | pass | Every check has `passed: true`. |
| V-10 | Data | Split is 10 plus 10, disjoint, 5/5 and 7/3 | Required | pass | 10 eval, 10 dev, overlap 0, eval positives 5, dev positives 7. |
| V-11 | Stub | Stub run creates all five files | Required | pass | `/tmp/doc-pipe-runs/<run_id>/`. |
| V-12 | Stub | Stub prediction is `not_found` with no span | Required | pass | One row, `char_start: null`. |
| V-13 | Artifacts | Manifest has every required field | Required | pass | `missing []`. |
| V-14 | Artifacts | Predictions, errors, and logs are valid JSONL | Required | pass | All three files parse. |
| V-15 | Evidence | Every found span slice equals its quote | Required | pass | Live positive run slice matches. |
| V-16 | Errors | Duplicate quote produces `quote_not_unique` | Required | pass | `tests/test_evidence.py`, `tests/test_graph.py`. |
| V-17 | Errors | Missing quote produces `quote_not_found` | Required | pass | `tests/test_evidence.py`, `tests/test_graph.py`. |
| V-18 | Errors | Schema error produces `invalid_output` | Required | pass | `tests/test_llm.py`, `tests/test_graph.py`. |
| V-19 | Errors | Context overflow produces `context_overflow` | Required | pass | `tests/test_llm.py`, `tests/test_graph.py`. |
| V-20 | Errors | Timeout or high cost produces `budget_exceeded` | Required | pass | `tests/test_llm.py`, `tests/test_graph.py`. |
| V-21 | Errors | Auth or network failure produces `operational_error` and exit 1 | Required | pass | `tests/test_llm.py`, `tests/test_graph.py`. |
| V-22 | Logs | Logs contain the expected events | Required | pass | All eight events present. |
| V-23 | Logs | Logs contain no secrets or full contract text | Required | pass | `tests/test_logging.py`; secret and text redacted. |
| V-24 | Tracing | Tracing is off when env is unset | Required | pass | `tests/test_tracing.py`. |
| V-25 | Tracing | Tracing is on when env is set and key is present | Manual | not-run | Manual check not performed. |
| V-26 | Live | Evaluation-positive contract completes | Manual | pass | Run `20261030T095647Z-d2b360bb`, status `found`. |
| V-27 | Live | Evaluation-negative contract completes or records an error | Manual | pass | Run `20261030T095703Z-9f96f9be`, status `not_found`. |
| V-28 | Live | Cost is at most 0.50 USD per contract | Manual | pass | Positive 0.070812 USD; negative 0.002932 USD. |
| V-29 | Live | Latency is at most 60 seconds per contract | Manual | pass | Positive 3.645 s; negative 1.515 s. |
| V-30 | Security | No `.env`, AWS key, or LangSmith key is staged | Required | pass | `.env` is ignored; staged files checked before commit. |

## 14. Sign-off

| Field | Value |
| --- | --- |
| Feature | Governing-law live extraction |
| Plan version | 1.0 |
| Verification date | 2026-10-30 |
| Executed by | Implementation agent |
| Required gates | ruff, ruff format, pytest all pass |
| Advisory findings | pyright reports 0 errors |
| Open failures | none |
| Decision | approve |
| Notes | V-25 manual tracing check remains not-run. |

Sign-off is complete only when every required row is `pass` or has an approved exception.
Manual rows may be `blocked` with a recorded reason.
