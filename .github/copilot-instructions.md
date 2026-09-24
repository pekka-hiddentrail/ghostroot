# GHOSTROOT — Copilot instructions

Read `CLAUDE.md` at the repo root first — it's the full instruction set
(working process, code/test/commit conventions, plain-writing rule) and
applies here too. This file exists only because Copilot doesn't read
`CLAUDE.md` automatically.

Highest-priority rules, if you read nothing else: this project is a
from-scratch rewrite (v2) — `v0.1-archive/` is retired, don't extend or
fix it. `docs/SPEC.md`, `docs/METHODOLOGY.md`, `docs/ARCHITECTURE.md`,
`docs/LANGUAGE.md` are the source of truth for design; reference them,
don't restate or contradict them. Deterministic by default — exactly one
task needs an LLM (`ARCHITECTURE.md` §11); justify any LLM call against
that before adding one. No magic numbers — ground a threshold
statistically or state the reason.
