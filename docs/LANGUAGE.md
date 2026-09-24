# Language generation ruleset

How to generate *any* plausible instance of the Ghost Language — not a
description of one specific generated language. That's a separate, later
artifact (see "Releasable syllabus" below).

## Two independent axes

- **World seed**: which specific Ghost Language this run is — its
  consonant/vowel inventory, syllable shapes, baseline word order, which
  formula archetypes it uses. Rolled once at world creation.
- **Diachronic mutation** (`ARCHITECTURE.md` §8/§12): how that chosen
  language changes across its own attested history. Independent of the
  world seed — operates on whatever got rolled.

Correction to §8/§12: diachrony isn't only growth. Real language change
adds, mutates, *and* reduces — case syncretism, phonemic mergers, a
grammaticalized marker eroding away. The latent-category inventory and
phonology should be able to shrink or shift, not just accumulate.

Diachronic sound mutation is grounded in the **Index Diachronica**
(chridd.nfshost.com/diachronica — a searchable compilation of attested
sound changes across many real language families, built for naturalistic
diachronic conlanging). Same relationship as PHOIBLE to the phoneme
system: it grounds *which mutations are realistic* (lenition,
palatalization, final-vowel loss, consonant shifts) instead of picking
diachronic moves arbitrarily.

## Phoneme system

Grounded in PHOIBLE (2,186 languages, real cross-linguistic inventories —
phoible.org, github.com/cldf-datasets/phoible), used for statistical
shape, not literal borrowing:

- **Inventory size** drawn from PHOIBLE's real size distribution (very
  small ~11-phoneme inventories to very large 100+, typical range
  concentrated around 20–37 consonants) — not fixed.
- **Place and manner of articulation** drawn from real aggregate
  frequency (which places/manners are cross-linguistically common vs.
  rare), computed from PHOIBLE's `inventories.csv`/`parameters.csv` at
  implementation time — not hand-guessed percentages. This gives each
  world a plausible-but-not-copied consonant system.
- **Vowel system** drawn independently, its own size/quality distribution
  — not tied to the consonant draw.
- **Syllable shapes** drawn independently again, from typological
  syllable-canon frequency (plain CV-dominant vs. cluster-tolerant, etc.)
  — not inherited from whichever real language the consonant draw happens
  to resemble.

Each axis independent is what avoids "a real language with one thing
swapped": realism per axis, uniqueness in combination.

## Baseline word order

One fixed default order per world seed (e.g. a plain unmarked
constituent order) — the thing diachronic category effects (passive
inversion, etc.) perturb. Not per-branch templates (one language, no
branches).

## Formula archetypes

A growing, named catalog of context-bound templates, e.g.:

- `funerary_genealogy` — "X, son of Y, son of Z, dies at age N"
- `ledger_trade` — "trade: commodity A for commodity B, person C, person D"
- `road_marker` — "place-name, N paces"

Each entry: slot structure, and which genres/site-types it's eligible for
(a burial site draws heavily from `funerary_genealogy`; a road post from
`road_marker`). A world seed uses a subset of the catalog, not all of it —
matches `ARCHITECTURE.md` §10's "few templates, high coverage within
their genre."

## Demo worlds

The near-term goal isn't one locked canonical language — it's the ruleset
producing varied, distinguishable worlds now, for bug-hunting and for
actually playing with the system. "Demo" means worlds we generate
ourselves for testing, never real-world language data. Locking a canonical
instance is a later decision, made once the ruleset is solid.

## Releasable syllabus (later)

A human-readable phonology/lexicon/grammar sketch, auto-generated from one
specific world-seed's actual state — not hand-authored, not this document.
Stays outside the epistemic boundary (never readable by reconstruction
code) but is a real, well-formatted artifact a human can read — the
in-universe "answer key," and a fun output in its own right. Deferred, not
designed here.
