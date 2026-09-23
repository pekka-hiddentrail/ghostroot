# Real-world reconstruction methodology

This document surveys how actual historical linguists and epigraphists
approach a corpus like the one GHOSTROOT simulates: a legible script,
an unfamiliar language, no bilingual anchor, and a growing pile of finds
over time. It's the empirical grounding for issue #1 (grammar scope) and
feeds the deterministic-vs-LLM boundary (#5) and data model (#6).

Two families of method exist. **Comparative** methods (compare a language
against known relatives) don't apply to us — SPEC.md establishes there are
no known relatives, only a script that outlived the language. Everything
below is **internal** method: squeezing structure out of one language's own
corpus, which is exactly our situation and exactly how real philologists
work when no bilingual anchor exists.

## 1. Distributional analysis (the actual basis for "meaning from context")

Zellig Harris's distributional hypothesis, and J.R. Firth's "you shall know
a word by the company it keeps": words that occur in similar contexts tend
to have related meanings or grammatical roles. Concretely, in a corpus, this
means:

- Recording, for every word, the *set of words/signs that occur immediately
  before and after it* across all attestations (a concordance / KWIC —
  "keyword in context" — index, standard corpus-linguistics tooling).
- A word with a narrow, consistent set of neighbors is likely playing a
  fixed grammatical role (a case marker, a particle). A word whose neighbor
  set is wide and varied is more likely a content word free to combine with
  many things.
- This is a real, mechanical, corpus-internal technique — no translation
  needed, just co-occurrence statistics.

## 2. Frequency analysis / Zipf's Law

Word frequency in any natural-language corpus follows a power-law
distribution: a handful of words (function words — articles, conjunctions,
common particles) account for a large share of total tokens; most words are
rare, occurring once or a few times ("hapax legomena"). This is measurable
and diagnostic:

- High-frequency + broad distribution across genres/find-contexts →
  function word (grammatical role, not concrete meaning).
- Low-to-mid frequency + clustered in one genre/context → content word tied
  to that domain.
- Concretely: the generator should have function-like words scatter across
  contexts and content-like words cluster by domain, so this statistic is
  genuinely there to be found — and detection should be a direct
  computation over the corpus, not an LLM eyeballing a handful of examples.

## 3. Paradigm-finding via alternation — Alice Kober's method (Linear B)

Before Michael Ventris's 1952 breakthrough (that Linear B encoded Greek),
Alice Kober made the key structural progress using nothing but internal
analysis: she found sets of words sharing a common stem but differing in
their final sign(s) — "Kober's triplets" — and built a grid showing which
sign-alternations recurred together across many such sets. This let her
establish that Linear B had case-like inflection (a grammatical paradigm)
*without knowing what a single word meant* — purely from positional/
alternation statistics.

This maps directly onto morphology detection for us: cluster words by shared
stem (longest common prefix/substring across otherwise-different forms),
look for a small closed set of alternating endings recurring across many
such clusters. If found, that's real evidence of an inflectional paradigm —
independent of any semantic gloss.

## 4. Formulaic phrase detection

Real epigraphic corpora of this kind (funerary, administrative, votive) are
dominated by fixed formulae: Egyptian offering formulas, Etruscan funerary
formulas ("this is the tomb of X, son of Y, who lived N years" — recurring
almost verbatim across the Etruscan corpus), Linear B administrative tallies
following a fixed template. Detecting a repeated multi-word sequence across
independently-found texts is strong, mechanical evidence (an n-gram/longest-
common-subsequence search across the corpus), and formula slots that *vary*
between instances (the name, the number) are themselves informative — a
slot that always holds a short, unique, non-repeating token across instances
is a strong proper-noun/numeral candidate.

## 5. Context-driven semantic anchoring

Before any word is translated, archaeological context supplies the first
real hypotheses: a word appearing only in burial contexts is plausibly
funerary vocabulary; a word appearing on tally-like objects alongside
apparent numerals is plausibly a commodity or unit. This was literally part
of how Egyptian hieroglyphs were approached before Champollion — royal names
were hypothesized from cartouches' position and repetition in monumental/
funerary contexts before a single sound value was confirmed. This is
directly what a "find" (issue #2) needs to carry as metadata: site, material,
genre — the same information real epigraphists lean on first.

## 6. Named-entity / proper-noun spotting

A concrete, well-established sub-technique: proper nouns (personal names,
place names, titles) are often identifiable before any grammatical or
lexical translation, because they recur in expected structural positions
(e.g. after a formula slot for "son of ___"), don't inflect the same way
common nouns do, and — when known geography/history exists — can sometimes
be cross-checked (Ventris compared candidate Linear B place-names against
known Cretan geography). For us, a proper-noun layer is detectable purely
from formula-slot position and lack of ordinary inflectional alternation
(see #3), without needing any external cross-check.

## 7. Corpus-level statistical validity checks

Before assuming a corpus is even "a language" in the full sense, real
scholarship asks whether its sign sequences behave like language at all —
e.g. the Rao et al. (2009) conditional-entropy study of the (still
undeciphered) Indus script, comparing its statistical structure against
known linguistic scripts vs. non-linguistic sign systems. This is a sanity-
check layer, not a translation method: it tells you whether the positional/
statistical patterns you're finding are meaningful at all, which is directly
relevant to validation (issue #6) in the "no hidden answer key" framing from
SPEC.md §5 — internal statistical coherence is itself evidence.

## 8. Paleographic and stratigraphic dating → diachronic layering

Because our premise has finds spread over a real span of time (new sites
turning up later, carbon-dated), the corpus isn't a single frozen snapshot —
it's diachronic, the way a real epigraphic tradition is dated by letter-form
evolution (paleography) and archaeological stratigraphy. This means the
techniques above (1–6) should be run *within date bands*, not just over the
whole corpus at once, so that genuine language change over time doesn't get
mistaken for synchronic variation (or vice versa) — and opens a real
additional structural question about how much diachronic drift the
generator should model at all (worth folding into issue #3's latent-
variation design).

## 9. What we deliberately don't have

No bilingual anchor (no Rosetta Stone, no Behistun trilingual) — that's the
method real Egyptological/Old Persian decipherment leaned on hardest, and
it's explicitly not available here per the premise (single unrelated
language, no known translation). Everything above is chosen because it
works *without* one. One channel worth flagging as a genuine possibility
raised by the premise itself, for later consideration (not yet in scope):
if the script was inherited by the later known traditions, isolated
loanwords or substrate vocabulary might plausibly have survived into them —
a thin, indirect echo of Ghost Language vocabulary, distinct from a full
bilingual anchor. Flagging, not deciding, since it's a scope question.

## How this answers issue #1 (grammar scope)

Grammar reconstruction should cover what techniques #1–#6 can actually
recover from a monolingual internal corpus:

- **Morphology**: paradigm detection via stem/alternation clustering
  (Kober-style, §3) — in scope, and mechanical/deterministic.
- **Word order / syntax**: positional co-occurrence statistics (§1) plus
  formula-template structure (§4) — in scope, deterministic.
- **Proper nouns**: formula-slot position + non-inflecting behavior (§6) —
  in scope, deterministic.
- **Semantics/meaning**: anchored first by context (§5, deterministic
  correlation), refined into an actual English-language gloss only where
  real judgment is needed (§5's *labeling* step is the legitimate LLM task —
  everything upstream of it is mechanical).
- **Internal reconstruction depth**: bounded by what's achievable without a
  bilingual anchor (§9) — deep enough to find paradigms and formulae, not
  deep enough to fully resolve abstract semantics without judgment.
