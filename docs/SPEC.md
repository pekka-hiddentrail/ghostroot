# GHOSTROOT v2 — Design Spec

## 1. Premise

Archaeologists find an inscription in a script resembling a known
historical writing system (the real-world example is arbitrary and
illustrative — any script later adopted by other, well-documented
languages fits: think "Brahmi-derived script now read via several known
descendant traditions," not a specific pairing). It's initially catalogued
as that known tradition. Carbon dating places it well before any attested
speaker of the languages that tradition is known for. More sites turn up
over time — different materials (clay, stone, palm-leaf) — all using the
same writing system.

The writing system is older than the traditions that later used it: it
was inherited and adapted by them, the way scripts get borrowed and
repurposed across unrelated languages throughout history. Because those
later languages are well documented, sign-to-sound values are essentially
known — the inscriptions can be *read* with confidence. What they *say* is
a different question. The language actually encoded predates and is
unrelated to anything attested — a single extinct language, known only
through a slowly growing pile of finds, understood on its own terms.

This is the Ghost Language. GHOSTROOT simulates reconstructing it — not by
comparing sibling descendant languages (there are none, only a script that
outlived it), but the way real epigraphists work when a script is legible
but the language isn't understood yet: Etruscan (read via a Greek-derived
alphabet, understood only slowly and still only partially), Meroitic (read
via Egyptian-derived signs, still poorly understood as a language).

## 2. Why this

Building a *constructed* language for a fictional world always felt
artificial — deciding up front what the sound system and grammar "should"
be. The more interesting problem is the reverse: discover a plausible
ancient language as if excavating it, rather than design it. The corpus
should feel found, not authored — irregular, incomplete, contradictable —
and the reconstructed grammar and vocabulary should emerge from evidence
across a growing dig, not be decided in advance.

## 3. Structural shape

- **One language**, not diverging branches. No comparative method across
  siblings — many attestations of a single extinct language, accumulated
  over simulated archaeological time as new sites are found.
- **The script is legible.** Sign-to-sound transliteration is a given,
  inherited fact, not something to reconstruct. Every inscription is
  already phonetically transcribed, readable text from the moment it's
  generated. This system is never about cracking an unread script.
- **The mystery is grammar, vocabulary, and meaning** — reconstructed from
  the corpus's own internal patterns and each find's physical/contextual
  metadata (site, material, genre), not from any known relative.

## 4. Methodology grounding

No sibling language to compare against, so the real analogue is epigraphic/
philological analysis of a corpus that's readable but not understood. Core
toolkit (see `docs/METHODOLOGY.md` for the real-world precedents):

- Frequency/distribution statistics — the basis for the distributional
  hypothesis (function words spread thin and flat; content words cluster
  by domain).
- Formulaic phrase detection — repeated multi-word sequences across
  independent finds.
- Positional/syntactic pattern-finding within the corpus itself.
- Internal reconstruction — morphological alternations within the one
  language, not cross-branch correspondence.
- Context-driven semantic hypothesis formation — meaning approached
  through material, site, genre, co-occurring signs.

## 5. Ground truth is emergent, not fixed

There is no static, complete, hidden answer key the generator holds and
the pipeline gets scored against — that implies a single predetermined
correct grammar waiting to be matched, which isn't how real reconstruction
works.

Instead:

- The generator produces variation that can stem from a real latent cause
  (a word-order shift might reflect passive voice, tense/mood, register)
  — but that cause is never pre-labeled or exposed as a table the pipeline
  could read. The generator's mechanism is the raw phenomena, not the
  answer.
- "Ground truth" is whatever theory the research process has converged on
  with enough evidence — provisional, "canonized" only once well-supported,
  like Grimm's Law or laryngeal theory: accepted because they kept
  explaining new data, revised or overturned when they eventually didn't.
- A canonized theory constrains what's generated/interpreted next —
  evidence shapes theory, theory shapes future generation. Two-way, not
  "hidden truth leaks down to a guesser."
- Multiple coherent theories can fit the same data. There may be no single
  "correct" grammar, only better- or worse-supported explanations — same
  as real scholarly disagreement over, say, Etruscan grammar.

Validation follows from this: internal coherence and predictive power over
new data, not "% match to a hidden table."

## 6. Epistemic boundary

The reconstruction pipeline may only ever read:

- **`finds`/`tokens`** — transliterated text plus site/material/genre/
  date-band metadata. What was dug up, nothing more.
- **Its own derived tables** — paradigm clusters, formulae, candidate
  semantic fields, canonized theories from this or a prior pass.

It never reads the generator's internal latent state directly — *why* a
word order inverted (passive voice, tense, register) stays invisible; only
the surface effect (the row in `finds`/`tokens`) is visible.

Canonization is the one sanctioned crossing, one-directional: the pipeline
writes a canonized theory to **`canon`**; the generator reads `canon`
before its next find, so it won't contradict settled theory. The generator
never writes to `canon`; the pipeline never reads generator state, only
`canon`'s own contents. This makes §5's "evidence shapes theory, theory
constrains future generation" structurally enforced, not just convention.
