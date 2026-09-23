# Mechanism design: storage and pseudocode

For each real technique in docs/METHODOLOGY.md, this works out what data it
actually needs, what storage/architecture fits, and the shape of the
algorithm — design documentation before any implementation, per issue #1
and the "different mechanisms may need different architectural choices"
question.

## 0. Overall storage recommendation: SQLite as the primary store

Nearly every mechanism below reduces to a relational query — count, group
by, join, having — over two basic facts: **which sign/word occurred where**,
and **what metadata that find carries** (site, material, genre, date-band).
That's exactly what a real database is for, so:

- **SQLite** (Python stdlib `sqlite3`, no new dependency) is the corpus's
  primary store. The corpus grows incrementally (new finds inserted over
  time, matching "new digs"), most mechanisms are aggregate queries
  (`GROUP BY`, `COUNT`, `JOIN`) that SQL expresses directly, and it's a
  single file — easy to snapshot, version, inspect.
- **RAG (embedding/vector retrieval)** is reserved for narrowing context in
  the eventual LLM gloss-labeling step (see the LLM-dependency section
  below) — the core discovery mechanisms are statistical and positional,
  not semantic-similarity search, so RAG has no role there.
- Two **transient, in-memory** structures sit on top of SQLite for specific
  mechanisms (not persistent stores in their own right): a **trie** for
  stem/alternation clustering (§3), and stdlib `difflib`-based alignment for
  formula-slot detection (§4). Both are built from data pulled out of SQLite
  and their *results* are written back as new SQLite tables.

## 1. Core schema (shared by all mechanisms)

```sql
CREATE TABLE finds (
    find_id     INTEGER PRIMARY KEY,
    site        TEXT,
    material    TEXT,
    genre       TEXT,
    date_band   INTEGER,   -- coarse chronological bucket, see ARCHITECTURE §8
    discovered_at INTEGER  -- in-simulation "dig time" this find entered the corpus
);

CREATE TABLE tokens (
    token_id    INTEGER PRIMARY KEY,
    find_id     INTEGER REFERENCES finds(find_id),
    position    INTEGER,   -- position within the find's text
    form        TEXT,      -- surface wordform, already transliterated; NULL = lacuna (see below)
    sign_type   TEXT       -- 'alphabetic' | 'numeral', see ARCHITECTURE §9
);

CREATE INDEX idx_tokens_form ON tokens(form);
CREATE INDEX idx_tokens_find_pos ON tokens(find_id, position);

CREATE TABLE canon (
    theory_id   INTEGER PRIMARY KEY,
    statement   TEXT,      -- the canonized theory itself
    evidence    TEXT,      -- what supports it (derived-table references)
    canonized_at_band INTEGER  -- date-band at which it was accepted
);
```

`canon` is the one sanctioned crossing point between generation and
reconstruction (SPEC.md §6): the reconstruction pipeline writes to it, the
generator reads it before producing its next find, and never the reverse.

**Condition/completeness**: real finds are routinely damaged — breaks,
erosion, decay — and material predicts damage rate directly (organic media
like palm-leaf degrade far more readily than stone or fired clay). A `find`
has a condition (`complete` / `damaged` / `fragmentary`), and a damaged
find's `tokens.form` can be `NULL` at a known `position` — a lacuna: the
position (and often the fact that *something* was there) is still known
from spacing/layout on the physical object, but its content isn't legible.
Damage probability should scale with material (highest for organic media,
lowest for stone/fired clay) and possibly with how far back a find's
date-band is (older strata disturbed more). This is a deliberate difficulty
lever, not incidental noise: real philology routinely reconstructs a
damaged formula slot from the surrounding pattern (§5), so lacunae give the
formula/paradigm mechanisms something genuine to demonstrate.

Every mechanism below is a query or an algorithm over `finds`/`tokens`,
writing its findings into its own derived table.

## 2. Distributional analysis (concordance / KWIC)

**Storage**: a view/query over `tokens`, no new table needed for the raw
statistic (materialize into `neighbor_stats` only if it's queried often
enough to be worth caching).

```sql
-- neighbor distribution for a given word
SELECT t2.form AS neighbor, COUNT(*) AS n
FROM tokens t1
JOIN tokens t2 ON t2.find_id = t1.find_id AND t2.position = t1.position + 1
WHERE t1.form = :word
GROUP BY t2.form
ORDER BY n DESC;
```

Pseudocode for "how narrow is this word's neighbor set" (the function-word
signal from METHODOLOGY.md §1):

```
for each distinct form in tokens:
    neighbors = distinct (prev_form, next_form) pairs across all occurrences
    breadth = len(neighbors) / occurrence_count(form)
    # low breadth relative to occurrence count -> fixed grammatical role
```

## 3. Frequency analysis / Zipf check

**Storage**: none new — an aggregate query on `tokens` joined to `finds`.

```sql
SELECT form, COUNT(*) AS freq, COUNT(DISTINCT genre) AS genre_spread
FROM tokens JOIN finds USING(find_id)
GROUP BY form
ORDER BY freq DESC;
```

`genre_spread` relative to `freq` is the mechanical version of "scatters
across contexts vs. clusters in one" — no LLM needed to notice it.

### A note on thresholds: significance tests, not magic numbers

§4 and §5 below need a way to decide "is this recurrence real, or could it
plausibly be chance?" Rather than a hand-picked constant (`MIN_SUPPORT = 3`,
`MIN_STEM_LEN = 2`), that question has a standard, real answer: a
**permutation/null-model test**, the same style of check used in real
corpus statistics (e.g. the Rao et al. 2009 conditional-entropy comparison
for the Indus script, METHODOLOGY.md §7).

```
def is_significant(observed_count, corpus, statistic_fn, trials=1000, alpha=0.05):
    null_counts = []
    for _ in range(trials):
        shuffled = shuffle_tokens_within_finds(corpus)   # break real sequence, keep corpus size/shape
        null_counts.append(statistic_fn(shuffled))
    p_value = fraction(null_counts >= observed_count)
    return p_value < alpha
```

`shuffle_tokens_within_finds` randomizes token order while holding find
boundaries, vocabulary, and frequency distribution fixed — so the null
model asks "would a pattern this strong show up in randomly-ordered text
with the same vocabulary," not "is it below some arbitrary count." `alpha =
0.05` is the one remaining constant, and it's a standard statistical
convention, not a domain-specific tuning knob. §4/§5's `MIN_SUPPORT` and
`MIN_STEM_LEN` become `is_significant(...)` calls using this test instead
of fixed thresholds.

## 4. Paradigm-finding via alternation (Kober-style)

**Storage**: derived table `paradigm_clusters(cluster_id, stem, members TEXT[])`.
**In-memory structure**: a trie, because grouping wordforms by shared prefix
is exactly what a trie is for (O(total characters) to build, walk multi-
child nodes to find alternation clusters directly, rather than an O(n²) all-
pairs comparison).

```
distinct_forms = SELECT DISTINCT form FROM tokens
trie = build_trie(distinct_forms)

for each trie node N with >= 2 children:
    endings = collect_suffixes_below(N)          # e.g. {-a, -om, -ei}
    recurrence = count_other_stems_sharing(endings)
    if is_significant(recurrence, corpus, statistic_fn=shared_ending_recurrence):
        record ParadigmCluster(stem=path_to(N), endings=endings)

write ParadigmClusters to paradigm_clusters table
```

The "recurs across multiple stems" check is what turns a coincidental
shared prefix into real paradigm evidence — a single stem with two endings
could be chance; the same ending *set* recurring under several unrelated
stems is a structural pattern.

## 5. Formulaic phrase detection

**Storage**: derived table `formulae(formula_id, template TEXT, slot_positions TEXT[], support INTEGER)`.

```
for n in [2..MAX_FORMULA_LEN]:
    ngrams = extract all n-length token sequences per find, with find_id
    group by exact sequence
    cross_find_count = COUNT(DISTINCT find_id) per group   -- cross-find, not just repeated within one find
    keep groups where is_significant(cross_find_count, corpus, statistic_fn=ngram_cross_find_recurrence)

-- slot-varying formulae (e.g. "X son of Y"):
for each pair of same-length ngrams with high similarity (difflib.SequenceMatcher
    over the token sequence, not characters):
    positions that differ = candidate slots
    positions that always match = the fixed template
    recurrence = count_other_pairs_sharing(template, slot_positions)
    if is_significant(recurrence, corpus, statistic_fn=formula_shape_recurrence):
        record Formula(template, slot_positions, support=recurrence)
```

`difflib` (stdlib) is the right tool here — this alignment happens *within*
one language's own formula instances, not across separate languages/
branches.

## 6. Context-driven semantic anchoring

**Storage**: none new — `tokens JOIN finds`, grouped by genre/site/material.

```sql
SELECT form, genre, COUNT(*) AS n
FROM tokens JOIN finds USING(find_id)
GROUP BY form, genre
ORDER BY form, n DESC;
```

A word whose counts concentrate in one genre row is the mechanical version
of "plausibly funerary/administrative/votive vocabulary" — this produces a
*candidate domain*, not a gloss; turning "clusters in funerary contexts"
into an actual English meaning is the legitimate LLM step (issue #5).

## 7. Named-entity / proper-noun spotting

**Storage**: none new — a composite query over `formulae` (§5) and
`paradigm_clusters` (§4).

```
candidates = tokens occupying a formula slot (from §5)
for each candidate form:
    if form does NOT appear as a member of any paradigm_cluster (§4)
       (i.e. it doesn't show the regular alternation pattern ordinary
       nouns/content words show):
        mark as proper-noun candidate
```

## 8. Diachronic layering

**Storage**: `finds.date_band` (already in the core schema) partitions
every query above — every mechanism in §2–§7 should be runnable with an
added `WHERE date_band = :band` (or `<=` for cumulative-to-date views),
not as a separate architecture.

Per the plain-first design decision: the generator's earliest date-band(s)
should produce grammar with fewer distinct grammatical categories (a
smaller paradigm-cluster inventory from §4, fewer formula variants from
§5), and later bands introduce more — mirroring real grammaticalization
(independent words becoming affixes/particles over time, categories like
tense/mood/aspect accumulating rather than being present from the start).
Concretely this means the *generator's* latent-category inventory (issue
#3) should itself be indexed by date-band, growing monotonically (or close
to it) as simulated time advances, rather than being a fixed-size set
present from the first find.

**Surface variation moves the opposite direction.** Real early written
traditions are typically *more* orthographically and syntactically variable
than mature ones: no scribal-school standardization yet, so the same word
gets spelled inconsistently across finds, and word order is looser/more
pragmatically driven before fixed constructions crystallize. As a tradition
institutionalizes, spelling conventionalizes and syntax rigidifies. So the
two axes move in opposite directions across date-bands:

- **Grammatical category count**: low → high (simple → more tense/mood/
  aspect/etc. as bands advance).
- **Surface variation** (spelling inconsistency for the same word,
  word-order looseness): high → low (freer/noisier early, standardizing
  later).

Both should be indexed by date-band alongside the latent-category inventory
(issue #3) — e.g. a per-band "orthographic noise rate" and "word-order
strictness" parameter that the generator applies when producing a find,
decreasing noise and increasing strictness as bands advance. This gives
§2–§7's mechanisms a real, present signal to detect (spelling variants of
the same word should actually cluster together early on; word order should
visibly tighten in later bands) rather than assuming a single fixed
generation model across the whole timespan.

## 9. Numeral sign-system as a separate glyph inventory

Real numeral systems are very often notated with dedicated signs, not
reused alphabetic letters — this should be modeled explicitly rather than
reusing the phonetic alphabet for numbers. Concretely:

- `tokens.sign_type` (core schema, §1) distinguishes `'alphabetic'` from
  `'numeral'` at generation time.
- The numeral glyph inventory is a small, closed set of symbols visually
  and positionally distinct from the alphabetic sign inventory — in our
  transliteration, rendered as characters that are neither letters nor
  modern digits (e.g. `¤ ¢ µ` or similar out-of-alphabet symbols), so a
  reconstruction pipeline can tell "this is the numeral system" apart from
  "this is the phonetic alphabet" the same way a real epigraphist can
  visually distinguish a numeral sign from a phonetic sign in an
  unfamiliar script, without knowing what either means yet.
- **Additive/cumulative to start** (repeated or grouped glyphs sum to a
  quantity — tally marks, Roman-numeral-style grouping), not positional
  place-value. Real numeral systems were additive for most of their
  history; place-value systems are a comparatively late invention. This
  also fits the diachronic growth principle (§8) directly: an additive
  system is genuinely simpler and belongs in the earliest date-bands, with
  a transition toward a more compact/positional scheme as a later-band
  stretch goal, not a first-cut requirement.
- Ledgers/administrative genres are the natural home for numeral tokens —
  this ties into §6's genre-clustering mechanism directly: numeral
  `sign_type` tokens should cluster heavily in administrative/ledger-genre
  finds, exactly the kind of realistic quirk worth generating deliberately
  (see also §10).

## 10. Generation-side implication: deliberate cultural formula quirks

For §5 (formula detection) to have real signal, the *generator* needs to
actually produce genuinely fixed formulae. The right way to size "not too
many" isn't a single corpus-wide percentage — it's **few distinct templates,
each with high coverage within its own genre**, which matches how real
formulaic epigraphy actually behaves: funerary epitaphs and administrative/
ledger records are typically dominated by one or two fixed shapes within
their genre (a large majority of instances follow the template, varying
only in the name/number slots), while votive or other free-form genres stay
much less formulaic. Concretely, for v2's first cut: **one fixed template
per genre that gets one at all** (e.g. one funerary formula, one ledger/
tally template using the numeral inventory from §9), applied to a clear
majority of that genre's finds — rather than many competing templates per
genre, or a low, corpus-wide sprinkle. This is a generation-design
requirement, not a reconstruction mechanism — flagged here because it
directly determines whether §5 has anything real to find, and belongs in
the same design conversation as issue #3 (latent-variation mechanism) and
issue #2 (find/genre schema).

## 11. What actually 100% requires an LLM

Going through every mechanism above, exactly **one** task has no
deterministic substitute:

- **Assigning an open-vocabulary English gloss/meaning to a word, formula,
  or reconstructed form**, given its distributional/contextual evidence
  (§2, §6). Frequency stats, genre-clustering, paradigm detection, and
  formula detection can all narrow a word down to *candidate semantic
  fields* (e.g. "clusters in funerary-genre finds, doesn't inflect like a
  common noun, sits in a fixed formula slot" → candidate: personal name or
  funerary-object noun) — but producing the actual English word or phrase
  that names the meaning requires real lexical/world knowledge no
  frequency table has. This is the one hard LLM dependency.

Everything else in §2–§8 is deterministic:

- Frequency/distribution statistics, genre-clustering into candidate
  semantic fields, paradigm/alternation detection, formula detection,
  proper-noun spotting, entropy/corpus-validity checks, and diachronic
  partitioning are all direct computation over the SQLite schema — no LLM
  involved, and none needed.
- Whether a theory gets "canonized" (SPEC.md §5) can also be a direct
  statistical test (does it keep correctly predicting/explaining new finds
  without contradiction) rather than an LLM judgment call.
- Narrating findings as readable prose for a human is a *soft* LLM use —
  wanted for a pleasant report, not required for the system to actually
  discover anything. A templated fill-in-the-blank summary works without
  one.

## 12. The generator's latent-variation mechanism, concretely

A small, sparse set of **latent grammatical categories** — voice, tense,
mood, register, clause-type — each with a small closed set of values,
introduced progressively by date-band (§8: none in the earliest band, one
or two added per later band). Each category value has a fixed **effect**: a
specific, deterministic transformation applied to a base clause when that
value is selected —

```
category_effects = {
    (voice, passive):  invert object/verb order, insert particle P,
    (tense, past):     append suffix from a closed set {-a, -en, ...},
    (mood, imperative): drop the subject token,
    ...
}
```

Two properties matter:

- **Regular, but not exceptionless.** An effect applies with high
  probability when its condition holds, not with certainty — real
  grammatical rules have real exceptions (analogy, sporadic change,
  register-driven optionality), and a mechanism that's 100% regular would
  make reconstruction trivially exact instead of genuinely uncertain.
- **Fully internal.** This table and the category values assigned to any
  given clause are never exposed through any API the reconstruction
  pipeline can reach (SPEC.md §6) — only the resulting `finds`/`tokens` rows
  are visible. The mechanism is real and consistent (that's what makes the
  corpus learnable at all — pure noise would have nothing to discover), it
  just isn't a privileged answer key.

Canonization (SPEC.md §5) interacts with this table only indirectly: the
reconstruction pipeline never reads it, but a *correct* theory about it
will keep succeeding against new finds (because the real mechanism keeps
producing consistent effects), while a *spurious* one will eventually be
contradicted — see §13.

## 13. Validation approach: temporal holdout, not table-matching

The corpus growing over simulated "dig time" already gives a natural held-
out set — no artificial train/test split needed. A theory canonized using
finds up to time T is validated against finds discovered *after* T:

```
def validate_theory(theory, new_finds):
    predictions = [theory.predicts(f) for f in new_finds if theory.applies_to(f)]
    hit_rate = mean(p.matched_observed_effect for p in predictions)
    return hit_rate, is_significant(hit_rate, corpus, statistic_fn=theory_hit_rate)
```

- Because the underlying mechanism isn't exceptionless (§12), no theory
  should be expected to reach a 100% hit rate — the bar is a hit rate
  significantly better than chance (the same permutation-test approach as
  the thresholds note above), not perfection.
- A **canonized** theory keeps its status while new finds keep supporting
  it at a significant rate. A hit rate that drops below significance, or a
  competing theory that scores significantly better on the same data, is
  the trigger for revision or replacement — the concrete mechanics behind
  SPEC.md §5's "revised or overturned when they eventually didn't."
- This is fair evaluation, not cheating: the pipeline is only ever scored
  against finds it could observe like a real researcher would (surface
  text + metadata), never against the generator's internal state.
