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
- JSON files as source of truth
- LLM backend is pluggable (`GHOSTROOT_BACKEND`: ollama, anthropic, or groq) via `llm.py` -- Ollama is
  no longer the only option, it was just too slow/unreliable to iterate against
- Word generation is also pluggable (`GHOSTROOT_WORD_GENERATOR`): `llm` asks the backend to invent
  nonsense fresh each call (no persistent structure); `phonotactic` (`protolang.py`) uses a small
  persistent proto-root pool with deterministic per-branch sound-change rules, so real cognates
  emerge across descendant "branches" instead of one-off noise
- Two separate, easy-to-confuse "lexicon" files: `data/proto_lexicon.json` is the hidden ground-truth
  root pool (gitignored, never shown to the researcher); `data/word_beliefs.json` is the researcher's
  emergent, evidence-accumulated interpretation of each lexeme (tracked in git, real output)
- See CLAUDE.md for the full architecture writeup

## Agent roles

### Speaker
- Generates short inscriptions
- No explanations
- Fragmentary output only

### Researcher
- Analyzes artifacts using the ENTIRE corpus history for a given lexeme, not just recent finds
- Proposes tentative proto-roots
- Must express uncertainty; confidence is derived from accumulated evidence, not asserted outright
- Leaves actionable open questions

## Data rules

Artifacts and research notes are append-only.
Schemas should not change casually.
A single lexeme (same branch + surface form) must never end up with contradictory interpretations
across different artifact instances -- update the shared belief entry, not one artifact at a time.

## What NOT to do

- Do not remove ambiguity
- Do not optimize for correctness
- Do not "solve" the language
- Do not let a lexeme's discovery context become pure decoration -- it's meant to be genuine
  (if noisy) distributional evidence, not flavor text

This project is epistemic art.
