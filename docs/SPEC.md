# GHOSTROOT v2 — Design Spec

Status: DRAFT — Premise and methodology grounding only. Not yet reviewed/approved.

## 1. Premise

Archaeologists find an ancient burial site bearing an inscription in a
script closely resembling a known historical writing system (the specific
real-world script is arbitrary and illustrative only — any script that was
later adopted by other, well-documented languages fits the premise; think
in the shape of "Brahmi-derived script now read via several known
descendant traditions," not a specific literal pairing). It's initially
catalogued as that known tradition. Carbon dating on the associated
material places it well before any attested speaker of the languages that
tradition is known for. More sites turn up over time — different
find-spots, different materials (clay tablets, carved stone, incised
palm-leaf) — all using recognizably the same writing system.

The resolution is this: the writing system is older than the known
traditions that later used it. It was inherited and adapted by them — the
way real scripts get borrowed and repurposed across unrelated languages
throughout history. Because those later languages are well documented, the
script's sign-to-sound values are essentially known: the inscriptions can
be *read* — transliterated into sound — with confidence. What they *say* is
a different question. The language actually encoded by the original
inscriptions predates and is unrelated to anything attested — a single
extinct language, known only through a slowly growing pile of physical
finds, that has to be understood on its own terms.

This is the Ghost Language. GHOSTROOT simulates reconstructing it: not by
comparing it against sibling descendant languages (there are none — it left
no known descendants, only a script that outlived it), but the way real
epigraphists work when a script is legible but the language behind it isn't
yet understood — cases like Etruscan (read via a Greek-derived alphabet,
genuinely understood only slowly, and still only partially) or Meroitic
(read via Egyptian-derived signs, still poorly understood as a language).

## 2. Why this, personally

This exists because building a *constructed* language for a fictional world
always felt artificial — deciding up front what the sound system and
grammar "should" be. The more interesting problem is the reverse: given
that a plausible ancient natural language could have existed, discover it
as if excavating it, rather than design it. The corpus should feel found,
not authored — irregular, incomplete, contradictable — and the reconstructed
grammar and vocabulary should be something that *emerges* from evidence
across a growing dig, not something decided in advance.

## 3. Structural shape (confirmed)

- **One language**, not several diverging branches. There is no comparative
  method across siblings here — the corpus is many attestations of a single
  extinct language, accumulated over (simulated) archaeological time as new
  sites and artifacts are "found."
- **The script is legible.** Sign-to-sound transliteration is a given,
  inherited fact (like reading Etruscan letters), not something to
  reconstruct. Every inscription in the corpus is already phonetically
  transcribed text — real, readable strings — from the moment it's
  generated. Nothing in this system is about cracking an unread script.
- **The mystery is entirely: grammar, vocabulary, and meaning.** Word
  segmentation, morphology, syntax, and what any of it actually *means* —
  reconstructed from the corpus's own internal patterns and from the
  physical/contextual metadata each find carries (site, material, genre —
  e.g. funerary, administrative, votive), not from any known relative.

## 4. Methodology grounding — what real epigraphists actually do

Since there's no sibling language to compare against, the real analogue is
epigraphic/philological analysis of an under-documented, undeciphered-*in-
meaning* (if not undeciphered-in-script) language corpus. The core toolkit,
concretely:

- **Frequency and distribution statistics.** Which signs/words are common
  vs. rare; which recur across many find-contexts (genre/site/material) vs.
  cluster tightly in one. This is the actual basis for the real
  distributional hypothesis (function words spread thin and flat; content
  words cluster by domain) — a legitimate, well-established technique (see
  docs/METHODOLOGY.md).
- **Formulaic phrase detection.** Real inscriptions of this kind are
  dominated by recurring formulae (funerary formulas, dedicatory
  boilerplate, administrative stock phrases) — finding a repeated multi-word
  sequence across independent finds is strong, mechanical evidence, closely
  analogous to how formulaic analysis cracked parts of many real corpora
  before full decipherment.
- **Positional/syntactic pattern-finding within the corpus itself.** Word
  order regularities, which word classes co-occur and in what sequence —
  discoverable from the corpus's own internal structure, without needing a
  second language to compare against.
- **Internal reconstruction.** Spotting morphological alternations by
  comparing forms that plausibly share a stem *within* the one language
  (e.g. a recurring affix pattern across many otherwise-different words),
  rather than cross-branch correspondence.
- **Context-driven semantic hypothesis formation.** A word's meaning is
  approached through where and with what it's found — material, site type,
  co-occurring signs/iconography, genre — the same contextual reasoning
  real archaeologists and epigraphists lean on before (or absent) a
  bilingual anchor.
  
## 5. Ground truth is emergent, not fixed

There is no static, complete, hidden answer key that the generator holds
and the reconstruction pipeline gets scored against. That framing implies a
single predetermined correct grammar waiting to be matched — which isn't
how real reconstruction works, and isn't how this should work either.

Instead:

- The generator produces *variation* that can stem from a real latent
  cause — a word-order shift might reflect passive voice, a tense/mood
  distinction, register, clause type, and so on — but that cause is not
  pre-labeled or exposed anywhere as a definitive table the pipeline could
  cheat by reading. The generator's underlying mechanism is the raw
  phenomena, not the answer.
- "Ground truth," in this system, is whatever theory the research process
  has converged on with enough supporting evidence — provisional, and only
  ever "canonized" (treated as settled) once well-supported, exactly like
  Grimm's Law or laryngeal theory in real historical linguistics: accepted
  because they kept explaining new data well, revised or overturned when
  they eventually didn't, never received as pre-existing fact.
- A canonized theory should act as a real constraint going forward: future
  generation and future interpretation should stay consistent with it
  rather than silently contradict it — this is a two-way relationship
  (evidence shapes theory; accepted theory shapes what's coherent to
  generate/interpret next), not one-way "hidden truth leaks down to a
  guesser."
- Multiple coherent theories can be compatible with the same data, and
  there may be no single "correct" grammar at all — only better- or
  worse-supported explanations, same as real scholarly disagreement over,
  say, Etruscan grammar.

This directly changes what "validation" can mean (see open items below):
not "% match to a hidden table," but something like internal coherence and
predictive/explanatory power over new data as it arrives.

## 6. Epistemic boundary

The reconstruction pipeline (every mechanism in docs/ARCHITECTURE.md) may
only ever read two things:

- The **`finds`/`tokens` tables** — surface transliterated text plus
  physical/contextual metadata (site, material, genre, date-band,
  discovered-at). This is "what was dug up," nothing more.
- Its **own derived tables** — paradigm clusters, formulae, candidate
  semantic fields, and canonized theories it or a prior pass produced.

It may never read the generator's internal latent state or decision
parameters directly — e.g. *why* a particular word order was inverted
(passive voice, a tense distinction, register) is exactly the kind of thing
that must stay invisible; only the surface *effect* (the inverted order,
as a `finds`/`tokens` row) is visible.

Canonization (SPEC.md §5) is the one sanctioned crossing, and it's
one-directional per generation step, not a leak: when the reconstruction
pipeline canonizes a theory, it writes it to a **`canon`** table. The
generator may read `canon` before producing its *next* find, so it doesn't
generate something that contradicts already-settled theory — but the
generator never writes to `canon`, and the reconstruction pipeline never
reads the generator's internal state directly, only `canon`'s own contents
(which it wrote itself). This keeps "evidence shapes theory; settled theory
constrains future generation" (§5) precise and structurally enforced,
instead of enforced only by convention/code review.

