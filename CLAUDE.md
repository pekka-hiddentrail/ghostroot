# CLAUDE.md

Guidance for Claude Code working in this repository.

## What this is

GHOSTROOT v2: a from-scratch rewrite of a simulation that reconstructs a
single extinct language from a growing archaeological corpus. The script is
legible (later reused by known languages); the mystery is grammar,
vocabulary, and meaning, discovered from the corpus's own evidence.

v1 is retired, archived under `v0.1-archive/`, tagged `v0.1`. Don't extend
or fix anything there.

Read in order before working here: `docs/SPEC.md` (premise, epistemic
boundary), `docs/METHODOLOGY.md` (real methodology this grounds in),
`docs/ARCHITECTURE.md` (storage/algorithm design). They're the source of
truth — reference them, don't restate or contradict them.

## Principles

- **Deterministic by default.** `ARCHITECTURE.md` §11: exactly one task
  needs an LLM (assigning an open-vocabulary gloss). Everything else is
  direct computation. Justify any LLM call against this before adding one.
- **Epistemic boundary** (`SPEC.md` §6): reconstruction code reads
  `finds`/`tokens`/its own derived tables, never the generator's internal
  state. `canon` is the one one-directional crossing.
- **Ground truth is emergent** (`SPEC.md` §5). Validate by temporal
  holdout + significance testing, never "% match against a hidden table."
- **No magic numbers.** Ground a threshold statistically or state the
  reason; never leave one unexplained.
- **Check for existing solutions before building.** Adopt a maintained
  library over hand-rolling (e.g. LingPy/LingRex, the reference MCP SQLite
  server). Verify current facts (API limits, model rankings) with a search
  instead of asserting from memory — this stuff goes stale fast.
- **Spec-first, one step at a time.** Settle a design question in the docs
  before building it. Work in small reviewable pieces, not big unreviewed
  batches — this project was rebuilt because v1 was "code until something
  happens."

## Code

- Python, stdlib-first; a new dependency needs a stated reason.
- Comments explain non-obvious *why*, for whoever reads this next — not
  *what* the code does, and not a note to Claude specifically.
- No premature abstraction.
- LLM-calling code stays in its own module, never inlined into a
  deterministic mechanism — the boundary should be visible on sight.

## Tests

- Deterministic mechanisms get unit tests against hand-built data with an
  exact expected answer.
- Tests may construct data using the generator's real mechanics; the
  epistemic boundary is for production code, not test fixtures.
- Fixed seeds for anything statistical. No live LLM calls in tests.
- Run the full suite before calling anything done.

## Commits and docs

- Small commits. Message says what changed *and why*; reference the doc
  section or issue it resolves.
- A bug fixed inline (no pre-filed issue) gets described in the commit
  message well enough to serve as the report.
- Keep the three docs in sync with reality as code lands.
- Remove an "open question" the moment it's answered — don't let resolved
  ones linger as text.
- Write plainly: no hedging filler, no unearned enthusiasm, no emoji
  unless asked, say the thing directly.

## Issues

- Label `v2-spec` = open design questions. File non-trivial work as an
  issue before starting it.
- Resolve by commenting the answer (point at the doc section) and closing
  — don't leave it open once it's actually settled.

## Commands

None yet — implementation hasn't started.
