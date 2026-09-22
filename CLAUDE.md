# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

GHOSTROOT is an agentic AI proof-of-concept that simulates the *process* of
reconstructing a lost proto-language from fragmentary evidence — not a
conlang generator. A speaker agent produces inscriptions in several
descendant "branches"; researcher agents analyze the growing corpus and
propose provisional, revisable hypotheses about proto-roots and grammar.

Core intent, carried over from this project's original design notes:
- Embrace uncertainty; allow wrong hypotheses; prefer revision over correctness.
- Treat language as *discovered*, not designed.
- Researcher agents must express uncertainty and leave open questions rather
  than "solving" the language.
- `data/artifacts.json`, `data/research_log.json`, and `data/research_questions.json`
  are append-only and tracked in git on purpose — they *are* the growing
  scholarly trail the project produces. Don't casually change their schemas.

## Commands

```
pip install -e .          # install in editable mode (required after any src/ layout change)
ghostroot                 # run one full cycle: speaker -> researcher -> belief update -> context check
ghostroot --speaker N      # bootstrap mode: run only the speaker N times, no analysis (use this to build
                           # up corpus size before analysis has enough data to find real patterns)
pytest                    # run tests
pytest tests/test_x.py -k test_name   # run a single test
ruff check .              # lint (line-length = 100, configured in pyproject.toml)
```

No build step; it's a plain `src/`-layout Python package (`src/ghostroot/`).

## Architecture

### Data flow per cycle (`run.py`)

1. Speaker generates one artifact (an `inscription` + matching `sentence`) for
   a randomly chosen branch, appended to `data/artifacts.json`.
2. `researcher.analyze_corpus` writes a narrative research note + proposes/updates
   structured research questions (`data/research_questions.json`).
3. `researcher.update_word_beliefs` updates the persistent lexeme belief store
   (`data/word_beliefs.json`) using the **entire** corpus history for each
   lexeme, then syncs the resulting interpretation onto every artifact that
   shares that lexeme — a single word never has two independently-guessed,
   contradictory meanings across different artifact instances.
4. `context_researcher.analyze_contextual_fit` cross-checks whether glossed
   meanings still make sense in the sentences they appear in.

### Two separate "lexicon" concepts — do not conflate them

- **`data/proto_lexicon.json`** (gitignored, built by `protolang.py`): the
  hidden ground-truth root pool the generator reads from. Never exposed to
  the researcher prompts. Treat it like `data/ground_truth.txt` (also
  gitignored) — an answer key, not something to leak into agent context.
- **`data/word_beliefs.json`** (tracked in git, built by `beliefs.py`): the
  researcher's emergent, evidence-accumulated guesses. This is real output,
  meant to be committed like the rest of the research log.

### Word generation: `llm` vs `phonotactic` (`GHOSTROOT_WORD_GENERATOR`)

- `llm` (default): asks the configured backend to invent nonsense fresh each
  call — no persistent structure, so there's nothing for the researcher to
  find beyond confabulation.
- `phonotactic`: `protolang.py` maintains a small persistent root pool. Each
  branch gets a fixed, deterministic set of sound-change rules derived from
  its name (`protolang._branch_rules`), so the same proto-root surfaces
  differently-but-relatedly across branches — this is what makes real,
  discoverable cognates possible instead of pure noise.

Each root also carries a hidden `role` (`structural` or `content`) and, for
content roots, a hidden `domain`. This governs which `discovery` context gets
attached to an artifact: structural roots (weighted ~3x more likely to be
picked, mirroring real function-word frequency) scatter uniformly across all
discovery contexts; content roots land in their own domain ~80% of the time.
The researcher is fed the resulting *distributional* stats (e.g. "5 distinct
contexts across 5 occurrences" vs "1 context across 5 occurrences") as
legitimate inference evidence — the distributional hypothesis (function words
spread thin and flat; content words cluster) — without ever seeing the hidden
role/domain labels themselves.

### Belief store keying

`beliefs.py` keys each lexeme by `(branch, surface_form)`, not by surface form
alone — the same string in two different branches is tracked as two separate
word identities. Whether they're actually cognates is left as a higher-level
hypothesis for the researcher's narrative, not assumed by the data model.
Confidence is derived from accumulated evidence (`evidence_for` /
`evidence_against`), not asserted directly by the LLM.

### LLM backend (`llm.py`)

Single `complete()` entry point dispatches to `ollama` / `anthropic` / `groq`
(`GHOSTROOT_BACKEND`), all via plain `urllib` HTTP calls — no SDK
dependencies. Groq's current catalog is reasoning models (`gpt-oss-*`, which
spend tokens on hidden reasoning before the visible answer) — calls to Groq
force `reasoning_effort: low` and a token floor, or short prompts come back
empty.

Model selection: `GHOSTROOT_SPEAKER_MODEL` / `GHOSTROOT_RESEARCHER_MODEL`
override the per-backend defaults in `config._DEFAULT_MODELS`.
