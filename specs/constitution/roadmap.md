# Roadmap

## Guiding rule

The first goal is a working prototype, not a platform.
Each phase ends with a runnable artifact and a measured result.
Complexity is added only when the baseline exposes a specific failure.

## Phase 0 - Bootstrap

Goal: get a runnable skeleton and confirm the data.

Work:
- Verify the CUAD revision, contract count, and governing-law label count.
- Define the governing-law Pydantic schema and prompt files.
- Define the LangGraph state and fixed graph skeleton.
- Build the local CLI and JSONL run layout.
- Add Ruff and Pytest.
- Add structured JSON logs.
- Configure LangSmith tracing through environment variables.

Exit criteria:
- The CLI starts and produces a manifest.
- The graph skeleton runs with stub nodes.
- The CUAD revision and label counts are documented.

## Phase 1 - Working prototype and evaluation baseline

Goal: run governing-law extraction end to end and record the first baseline.

Scope:
- One clause type: governing law.
- Input: CUAD plain text.
- Graph: `load_text -> extract -> validate -> persist -> score -> END`.
- No retry edge.
- No chunking.
- No Docling.
- Frontend: local Streamlit viewer over the JSONL artifacts.
- Evaluation: 10 held-out contracts, disjoint from prompt development.
- Evaluation sample: at least 5 contracts with a governing-law label and at least 5 without.
- Development sample: 10 separate contracts used only for prompt iteration.
- If the eligible pool cannot support the split, expand the sample and record the reason.

Work:
- Wire the graph nodes.
- Call Claude through Bedrock.
- Validate output with Pydantic.
- Derive the evidence span from the quote.
- Write `manifest.json`, `predictions.jsonl`, `errors.jsonl`, and `scores.json`.
- Report precision, recall, abstention accuracy, error counts, cost, and latency.
- Build the Streamlit viewer over the run artifacts.
- Show the contract text, clause, status, quote, span, errors, and metrics.

Exit criteria:
- The prototype runs end to end on all 10 evaluation contracts.
- The baseline report exists and is reproducible.
- Every found value has a valid quote and span.
- Every error is classified as wrong value, missed value, invented value, or invalid output.
- The baseline is recorded even if the initial targets are missed.
- The Streamlit viewer runs locally and displays the baseline run.

Initial targets:
- Precision >= 0.80.
- Recall >= 0.80.
- Abstention accuracy >= 0.95.

These targets guide the next iteration.
They are not Phase 1 gates.

Note:
With 10 evaluation contracts, 0.95 abstention accuracy is effectively a perfect score on the negative sample.
Treat the first number as a smoke signal.
Expand the evaluation set in Phase 2 when the improvement loop needs a sharper estimate.

## Phase 2 - Performance catch-up

Goal: use the baseline error list to improve extraction one change at a time.

Entry criteria:
- The Phase 1 baseline is recorded.
- The error list has been reviewed.

Method:
- Pick the largest error category first.
- Make one change at a time.
- Re-run the same evaluation set.
- Keep the change only if it improves the baseline without breaking evidence or abstention.
- Record each run.

Candidate changes:
- Prompt and context engineering.
- A single bounded retry after validation failure.
- Chunking, if the errors show long-context misses.
- Docling, if parser quality is the limiting factor.
- More clause types, after governing law is stable.
- Viewer improvements: run comparison, error filtering, and contract text highlighting.

Exit criteria:
- The chosen error category is measurably smaller.
- Precision, recall, and abstention do not regress.
- The run manifest and baseline comparison are recorded.

## Later phases

These are not committed.
Each requires a constitution update and explicit approval.

- API.
- Production UI and authentication.
- Database and query layer.
- Container and cloud deployment.
- Private contracts.
- Multi-user access control.
- Non-contract document types.
