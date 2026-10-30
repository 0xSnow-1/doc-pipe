# Mission

## Vision

Make contract clause extraction auditable and measurable for legal operations teams.
The system returns only structured values that are supported by the contract text.
It says "not found" when the clause is absent.
It never guesses.

## Problem

Commercial contracts contain important terms inside long, unstructured text.
Legal and back-office workers must read each contract to find those terms.
This is slow, and people make mistakes.

## Target audience

The primary user is a legal operations analyst who repeatedly extracts specific clauses from commercial contracts.
The user is not a lawyer seeking legal advice.
The system does not replace legal judgment.

## Core value

The system gives the user four things.
- Structured clause data instead of raw text.
- An exact supporting quote and character span for every extracted value.
- An explicit "not found" result when the clause is absent.
- A local viewer to inspect each extracted clause, its evidence, and the evaluation results.

## Product principles

### 1. Evidence over fluency

Every extracted value must include a quote from the source text and a character span.
A value without evidence is an error.

### 2. Abstention over guessing

If the clause is absent, or the system cannot support a value with evidence, it returns "not found".
It does not fill gaps with plausible text.

### 3. Measurement over assumption

Accuracy is measured against CUAD labels.
The project does not claim quality without per-field precision, recall, abstention accuracy, and an error breakdown.

### 4. Deterministic graph over autonomous agents

LangGraph is the workflow engine.
The graph has fixed nodes and fixed edges.
No node plans, selects tools, or chooses the next step.
The graph is not an agent.

### 5. Prototype before platform

The first goal is a small working pipeline that produces a measured baseline.
Complexity is added only when the baseline exposes a specific failure.

### 6. Show the work

A local Streamlit viewer is part of the prototype.
It shows the contract, extracted clause, quote, span, status, and run metrics.
It is a demo and inspection tool, not a production UI.

### 7. One document type at a time

The MVP handles commercial contracts only.
Other document types are added only after the contract pipeline works and is measured.

## What the system does

| It does | It does not |
| --- | --- |
| Find clause text in a contract | Give legal advice |
| Convert the clause to structured data | Decide whether a clause is good or bad |
| Return an exact quote and span for each value | Invent a value when evidence is missing |
| Say "not found" when the clause is absent | Answer questions across many documents |
| Show extraction, evidence, and metrics in a local viewer | Replace human legal review |

## Non-goals

The MVP does not include:
- Legal advice or clause quality judgment.
- A production user interface, authentication, or multi-user access.
- Search, retrieval, or question answering over multiple documents.
- Invoices, healthcare documents, claims, or other non-contract document types.
- Private or client contracts.
- Agentic planning or autonomous tool use.
- Model fine-tuning or custom model training.
- A database, API, container, or cloud deployment.

## Success definition

Phase 1 is complete when the prototype runs end to end on 10 held-out CUAD contracts and produces a repeatable evaluation baseline.
The baseline must report per-field precision, recall, abstention accuracy, error counts by type, cost, and latency.
Initial targets are 0.80 precision, 0.80 recall, and 0.95 abstention.
These targets guide the first improvement loop.
They do not block the baseline from being recorded.
Every found value must include a quote and character span that match the source text.
A local Streamlit viewer must display the baseline run and its evidence.

## Business goal

Establish a measured baseline and a short improvement loop before expanding scope.
Make the prototype visible to users and recruiters through a simple local viewer.
The evaluation harness and run artifacts are the source of truth for every later decision.
