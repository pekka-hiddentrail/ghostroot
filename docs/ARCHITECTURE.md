# Mechanism design: storage and pseudocode

What data each technique in `docs/METHODOLOGY.md` needs, what storage fits,
and the shape of the algorithm — before any implementation.

## 0. SQLite as the primary store

Nearly every mechanism below is a relational query — count, group by, join
— over two facts: **which sign/word occurred where**, and **what metadata
that find carries**. That's what a database is for.

- **SQLite** (stdlib `sqlite3`, no new dependency). The corpus grows
  incrementally (new finds over time), most mechanisms are aggregate
  queries SQL expresses directly, and it's a single file — easy to
  snapshot, version, inspect.
- **RAG** (embedding/vector retrieval) is reserved for narrowing context in
  the LLM gloss-labeling step (§11) — the discovery mechanisms are
  statistical/positional, not semantic-similarity search, so RAG has no
  role there.
- Three **transient, in-memory** structures sit on top of SQLite: a
  **trie** for stem/alternation clustering (§4), stdlib `difflib` for
  formula-slot detection (§5, aligning sequences of whole tokens, not
  characters), and LingPy phonetic alignment for spelling-variant
  recognition (§4a). All built from SQLite data; results written back as
  new tables.

## 1. Core schema

```sql
CREATE TABLE finds (
    find_id     INTEGER PRIMARY KEY,
    site        TEXT,
    material    TEXT,
    genre       TEXT,
    date_band   INTEGER,   -- coarse chronological bucket, §8
    condition   TEXT,      -- 'complete' | 'damaged' | 'fragmentary'
    discovered_at INTEGER  -- in-simulation "dig time" this find entered the corpus
);

CREATE TABLE tokens (
    token_id    INTEGER PRIMARY KEY,
    find_id     INTEGER REFERENCES finds(find_id),
    position    INTEGER,   -- position within the find's text
    form        TEXT,      -- surface wordform, already transliterated; NULL = lacuna
    sign_type   TEXT       -- 'alphabetic' | 'numeral', §9
);

CREATE INDEX idx_tokens_form ON tokens(form);
CREATE INDEX idx_tokens_find_pos ON tokens(find_id, position);

CREATE TABLE canon (
    theory_id   INTEGER PRIMARY KEY,
    statement   TEXT,      -- the canonized theory itself
    evidence    TEXT,      -- what supports it (derived-table references)
    canonized_at_band INTEGER
);
```

`canon` is the one sanctioned crossing between generation and
reconstruction (SPEC.md §6): reconstruction writes it, the generator reads
it before its next find, never the reverse.

**Condition/completeness**: real finds are routinely damaged, and material
predicts damage rate directly (organic media like palm-leaf degrade faster
than stone or fired clay). A damaged find's `tokens.form` can be `NULL` at
a known position — a lacuna: the position is known from spacing/layout,
the content isn't legible. Damage probability scales with material
(highest for organic, lowest for stone/clay) and possibly with how far
back the date-band is. This is a deliberate difficulty lever: real
philology reconstructs a damaged formula slot from the surrounding
pattern, so lacunae give the formula/paradigm mechanisms something real to
demonstrate.

Every mechanism below queries `finds`/`tokens`, writing findings into its
own derived table.

## 2. Distributional analysis (concordance / KWIC)

**Storage**: query over `tokens`; materialize into `neighbor_stats` only if
queried often enough to be worth caching.

```sql
-- neighbor distribution for a given word
SELECT t2.form AS neighbor, COUNT(*) AS n
FROM tokens t1
JOIN tokens t2 ON t2.find_id = t1.find_id AND t2.position = t1.position + 1
WHERE t1.form = :word
GROUP BY t2.form
ORDER BY n DESC;
```

"How narrow is this word's neighbor set" (the function-word signal,
METHODOLOGY.md §1):

```
for each distinct form in tokens:
    neighbors = distinct (prev_form, next_form) pairs across all occurrences
    breadth = len(neighbors) / occurrence_count(form)
    # low breadth relative to occurrence count -> fixed grammatical role
```

## 3. Frequency analysis / Zipf check

**Storage**: none new — aggregate query on `tokens` joined to `finds`.

```sql
SELECT form, COUNT(*) AS freq, COUNT(DISTINCT genre) AS genre_spread
FROM tokens JOIN finds USING(find_id)
GROUP BY form
ORDER BY freq DESC;
```

`genre_spread` relative to `freq` is the mechanical version of "scatters
across contexts vs. clusters in one."

### Thresholds: significance tests, not magic numbers

§4/§5 need to decide "is this recurrence real, or could it be chance?" —
not a hand-picked constant, a **permutation/null-model test** (same style
as Rao et al.'s 2009 Indus-script entropy comparison, METHODOLOGY.md §7):

```
def is_significant(observed_count, corpus, statistic_fn, trials=1000, alpha=0.05):
    null_counts = []
    for _ in range(trials):
        shuffled = shuffle_tokens_within_finds(corpus)   # break sequence, keep corpus size/shape
        null_counts.append(statistic_fn(shuffled))
    p_value = fraction(null_counts >= observed_count)
    return p_value < alpha
```

`shuffle_tokens_within_finds` randomizes token order while holding find
boundaries and vocabulary fixed, so the null model asks "would this show
up in randomly-ordered text with the same vocabulary." `alpha = 0.05` is a
standard statistical convention, the only remaining constant.

## 4. Paradigm-finding via alternation (Kober-style)

**Storage**: `paradigm_clusters(cluster_id, stem, members TEXT[])`.
**In-memory**: a trie — grouping wordforms by shared prefix is what a trie
is for (O(total characters) to build, vs. O(n²) all-pairs comparison).

```
distinct_forms = SELECT DISTINCT form FROM tokens
trie = build_trie(distinct_forms)

for each trie node N with >= 2 children:
    endings = collect_suffixes_below(N)          # e.g. {-a, -om, -ei}
    recurrence = count_other_stems_sharing(endings)
    if is_significant(recurrence, corpus, statistic_fn=shared_ending_recurrence):
        record ParadigmCluster(stem=path_to(N), endings=endings)
```

A single stem with two endings could be chance; the same ending *set*
recurring under several unrelated stems is a structural pattern.

### 4a. Spelling-variant recognition (LingPy)

§8 gives early date-bands real orthographic noise — the same word spelled
inconsistently before standardization. `paradigm_clusters` needs to
recognize "different spelling of the same word" separately from "genuinely
different word." This is phonetic similarity between two whole forms, not
positional/prefix clustering — LingPy's phonetic alignment is the right
tool (informed by which sound substitutions are plausible, unlike raw
character similarity), used here to merge variants within one language's
own vocabulary, not for cross-language cognate detection.

## 5. Formulaic phrase detection

**Storage**: `formulae(formula_id, template TEXT, slot_positions TEXT[], support INTEGER)`.

```
for n in [2..MAX_FORMULA_LEN]:
    ngrams = extract all n-length token sequences per find, with find_id
    group by exact sequence
    cross_find_count = COUNT(DISTINCT find_id) per group
    keep groups where is_significant(cross_find_count, corpus, statistic_fn=ngram_cross_find_recurrence)

-- slot-varying formulae (e.g. "X son of Y"):
for each pair of same-length ngrams with high similarity (difflib.SequenceMatcher
    over the token sequence — each token atomic, not character-level):
    positions that differ = candidate slots
    positions that always match = the fixed template
    recurrence = count_other_pairs_sharing(template, slot_positions)
    if is_significant(recurrence, corpus, statistic_fn=formula_shape_recurrence):
        record Formula(template, slot_positions, support=recurrence)
```

## 6. Context-driven semantic anchoring

**Storage**: none new — `tokens JOIN finds`, grouped by genre/site/material.

```sql
SELECT form, genre, COUNT(*) AS n
FROM tokens JOIN finds USING(find_id)
GROUP BY form, genre
ORDER BY form, n DESC;
```

Counts concentrated in one genre is the mechanical version of "plausibly
funerary/administrative/votive vocabulary" — a *candidate domain*, not a
gloss. Turning that into an actual English meaning is the LLM step (§11).

## 7. Named-entity / proper-noun spotting

**Storage**: none new — composite query over `formulae` (§5) and
`paradigm_clusters` (§4).

```
candidates = tokens occupying a formula slot (§5)
for each candidate form:
    if form does NOT appear in any paradigm_cluster (§4):
        mark as proper-noun candidate
```

## 8. Diachronic layering

**Storage**: `finds.date_band` partitions every query above — §2–§7 run
with an added `WHERE date_band = :band` (or `<=` for cumulative views),
not as separate architecture.

Two axes move in opposite directions across bands:

- **Grammatical category count**: low → high. Earliest bands have fewer
  distinct categories (smaller paradigm-cluster inventory, fewer formula
  variants); later bands add more — real grammaticalization (independent
  words becoming affixes/particles, categories accumulating over time).
  The generator's latent-category inventory (§12) is indexed by date-band,
  growing as simulated time advances.
- **Surface variation**: high → low. Early written traditions are
  typically *more* variable than mature ones — no scribal-school
  standardization yet, so the same word is spelled inconsistently and
  word order is looser. As a tradition institutionalizes, spelling
  conventionalizes and syntax rigidifies.

Both indexed by date-band alongside the latent-category inventory — a
per-band "orthographic noise rate" and "word-order strictness" the
generator applies, decreasing noise and increasing strictness as bands
advance. Gives §2–§7 a real signal: spelling variants cluster early,
word order visibly tightens later.

## 9. Numeral sign-system as a separate glyph inventory

Real numeral systems are usually dedicated signs, not reused alphabetic
letters.

- `tokens.sign_type` distinguishes `'alphabetic'` from `'numeral'` at
  generation time.
- Numeral glyphs are a small, closed set visually distinct from the
  alphabetic inventory — rendered as characters that are neither letters
  nor modern digits (e.g. `¤ ¢ µ`), so the pipeline can tell "numeral
  system" from "phonetic alphabet" the way an epigraphist can visually
  distinguish them in an unfamiliar script, without knowing what either
  means.
- **Additive/cumulative to start** (repeated/grouped glyphs sum to a
  quantity), not positional place-value — real numeral systems were
  additive for most of history; place-value is a late invention. Fits the
  diachronic growth principle directly: additive is simpler, belongs in
  earliest bands; positional is a later-band stretch goal, not a
  first-cut requirement.
- Ledgers/administrative genres are the natural home for numeral tokens —
  they should cluster there heavily, tying into §6 and §10.

## 10. Generation-side: deliberate cultural formula quirks

For §5 to have real signal, the generator needs genuinely fixed formulae.
Size it as **few distinct templates, each with high coverage within its
own genre** — real formulaic epigraphy has one or two fixed shapes
dominating a genre (funerary, ledger), not many competing templates or a
low corpus-wide sprinkle. First cut: one fixed template per genre that
gets one at all (one funerary formula, one ledger/tally template using
the §9 numeral inventory), applied to a clear majority of that genre's
finds.

## 11. What actually requires an LLM

Exactly **one** task has no deterministic substitute: **assigning an
open-vocabulary English gloss/meaning to a word, formula, or reconstructed
form**, given its distributional/contextual evidence. Frequency stats,
genre-clustering, paradigm detection, and formula detection can narrow a
word to *candidate semantic fields* ("clusters in funerary-genre finds,
doesn't inflect like a common noun, sits in a fixed formula slot" →
candidate: personal name or funerary-object noun) — but producing the
actual English word or phrase needs real lexical/world knowledge no
frequency table has.

Everything else is deterministic: frequency/distribution stats,
genre-clustering, paradigm/formula detection, proper-noun spotting,
entropy/validity checks, diachronic partitioning, and even theory
canonization (a direct statistical test, §13). Narrating findings as
readable prose is a *soft*, optional LLM use — a templated summary works
without one.

## 12. The generator's latent-variation mechanism

A small, sparse set of **latent grammatical categories** — voice, tense,
mood, register, clause-type — each with a small closed set of values,
introduced progressively by date-band (§8). Each value has a fixed
**effect**, a deterministic transformation applied to a base clause:

```
category_effects = {
    (voice, passive):  invert object/verb order, insert particle P,
    (tense, past):     append suffix from a closed set {-a, -en, ...},
    (mood, imperative): drop the subject token,
    ...
}
```

Two properties matter:

- **Regular, not exceptionless.** An effect applies with high probability
  when its condition holds, not certainty — real grammar has real
  exceptions. A 100%-regular mechanism would make reconstruction trivially
  exact instead of genuinely uncertain.
- **Fully internal.** Never exposed through any API the pipeline can
  reach (SPEC.md §6) — only the resulting `finds`/`tokens` rows are
  visible. The mechanism is real and consistent (that's what makes the
  corpus learnable at all), just not a privileged answer key.

Canonization interacts with this only indirectly: a *correct* theory keeps
succeeding against new finds; a *spurious* one eventually gets contradicted
— see §13.

## 13. Validation: temporal holdout, not table-matching

The corpus growing over simulated dig-time is a natural held-out set — no
artificial train/test split needed. A theory canonized using finds up to
time T is validated against finds discovered after T:

```
def validate_theory(theory, new_finds):
    predictions = [theory.predicts(f) for f in new_finds if theory.applies_to(f)]
    hit_rate = mean(p.matched_observed_effect for p in predictions)
    return hit_rate, is_significant(hit_rate, corpus, statistic_fn=theory_hit_rate)
```

- No theory should hit 100% (§12's mechanism isn't exceptionless) — the
  bar is significantly better than chance, not perfection.
- A canonized theory keeps its status while new finds keep supporting it
  significantly. A hit rate that drops below significance, or a competing
  theory that scores significantly better, triggers revision or
  replacement.
- Fair evaluation, not cheating: the pipeline is only ever scored against
  finds it could observe like a real researcher would, never against the
  generator's internal state.
