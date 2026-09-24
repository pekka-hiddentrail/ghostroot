# Real-world reconstruction methodology

How actual historical linguists and epigraphists approach a corpus like
ours: legible script, unfamiliar language, no bilingual anchor, a growing
pile of finds over time. Empirical grounding for grammar scope, the
deterministic-vs-LLM boundary, and the data model.

Comparative method (compare against known relatives) doesn't apply — no
known relatives exist, only a script that outlived the language. Everything
below is **internal** method: squeezing structure out of one language's own
corpus, exactly how real philologists work without a bilingual anchor.

## 1. Distributional analysis

Harris's distributional hypothesis, Firth's "you shall know a word by the
company it keeps": words in similar contexts share meaning or grammatical
role. Mechanically: record each word's immediate neighbors across every
attestation (a concordance/KWIC index — standard corpus-linguistics
tooling). A narrow, consistent neighbor set signals a fixed grammatical
role (case marker, particle); a wide, varied one signals a content word.
No translation needed, just co-occurrence counts.

## 2. Frequency analysis / Zipf's Law

Word frequency follows a power law: a handful of function words dominate
total tokens; most words are rare. High frequency + broad distribution
across genres → function word. Low-to-mid frequency + clustered in one
genre → content word tied to that domain. The generator should produce
this pattern for real (function-like words scattered, content-like words
domain-clustered), and detection should be direct computation, not an LLM
eyeballing examples.

## 3. Paradigm-finding via alternation — Kober's method (Linear B)

Before Ventris's 1952 breakthrough, Alice Kober found sets of words sharing
a stem but differing in final signs ("Kober's triplets"), and built a grid
of which alternations recurred together. This established Linear B had
case-like inflection *without knowing what any word meant* — pure
positional statistics. Maps directly to morphology detection: cluster
words by shared stem, look for a small closed set of alternating endings
recurring across many clusters. That recurrence is evidence of a paradigm,
independent of meaning.

## 4. Formulaic phrase detection

Real epigraphic corpora (funerary, administrative, votive) are dominated
by fixed formulae — Egyptian offering formulas, Etruscan funerary formulas
("this is the tomb of X, son of Y, who lived N years"), Linear B
administrative tallies. A repeated multi-word sequence across
independent finds is strong mechanical evidence (n-gram/LCS search).
Slots that *vary* between instances (name, number) are informative too: a
slot holding a short, unique, non-repeating token is a proper-noun or
numeral candidate.

## 5. Context-driven semantic anchoring

Archaeological context supplies the first hypotheses, before translation:
a word found only in burial contexts is plausibly funerary vocabulary; a
word beside apparent numerals on tally objects is plausibly a commodity.
Egyptian royal names were hypothesized from cartouche position/repetition
before any sound value was confirmed — same idea. This is why a "find"
needs site/material/genre metadata: it's the same information real
epigraphists lean on first.

## 6. Named-entity / proper-noun spotting

Proper nouns are often identifiable before any translation — they recur
in expected structural positions (after a "son of ___" formula slot),
don't inflect like common nouns, and can sometimes be cross-checked
against known geography (Ventris did this for Linear B place-names). For
us: formula-slot position + lack of ordinary inflection (§3) is enough,
no external cross-check needed.

## 7. Corpus-level statistical validity checks

Before assuming a corpus is language at all, real scholarship checks
whether its sign sequences behave like language — e.g. Rao et al.'s (2009)
conditional-entropy study of the (still undeciphered) Indus script against
known linguistic vs. non-linguistic sign systems. A sanity-check layer, not
a translation method: it tells you whether the patterns found are
meaningful, feeding directly into validation's "internal statistical
coherence is itself evidence" framing.

## 8. Paleographic/stratigraphic dating → diachronic layering

Finds span real time (new sites carbon-dated later), so the corpus is
diachronic, not a frozen snapshot — the way real traditions are dated by
letter-form evolution and stratigraphy. Techniques 1–6 should run *within*
date bands, not corpus-wide, so real language change over time doesn't get
mistaken for synchronic variation or vice versa.

## 9. What we deliberately don't have

No bilingual anchor (no Rosetta Stone, no Behistun trilingual) — the
method real Egyptological/Old Persian decipherment leaned on hardest, and
explicitly unavailable here. Everything above works without one. One
possible extra channel: if the script was inherited by later traditions,
loanwords or substrate vocabulary might have survived into them — a thin
echo of Ghost Language vocabulary, distinct from a bilingual anchor.
Tracked as issue #7, not decided.

## Grammar scope, answered

Grammar reconstruction covers what §1–§6 can recover from a monolingual
corpus:

- **Morphology** — paradigm/alternation clustering (§3). Deterministic.
- **Word order/syntax** — positional statistics (§1) + formula structure
  (§4). Deterministic.
- **Proper nouns** — formula-slot position + non-inflection (§6).
  Deterministic.
- **Semantics/meaning** — anchored by context (§5, deterministic), refined
  into an actual English gloss only where judgment is needed — the one
  legitimate LLM task; everything upstream is mechanical.
- **Depth** — bounded by what's achievable without a bilingual anchor
  (§9): enough to find paradigms and formulae, not enough to resolve
  abstract semantics unaided.
