# GHOSTROOT — Copilot Context

You are assisting with **GHOSTROOT**, an agentic AI proof-of-concept project.

This is not a chatbot.
This is a simulation of historical linguistics and scholarly reconstruction.

## Core intent

- Embrace uncertainty
- Allow wrong hypotheses
- Prefer revision over correctness
- Treat language as discovered, not designed

## Architecture

- Python project using src/ layout
- Local LLM inference via Ollama
- JSON files as source of truth
- No cloud APIs
- No token billing

## Agent roles

### Speaker
- Generates short inscriptions
- No explanations
- Fragmentary output only

### Researcher
- Analyzes artifacts
- Proposes tentative proto-roots
- Must express uncertainty
- Leaves actionable open questions

## Data rules

Artifacts and research notes are append-only.
Schemas should not change casually.

## What NOT to do

- Do not remove ambiguity
- Do not optimize for correctness
- Do not add cloud dependencies
- Do not "solve" the language

This project is epistemic art.
