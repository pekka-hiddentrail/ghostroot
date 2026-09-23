# v0.1 (archived)

This is the retired first implementation of GHOSTROOT, kept intact for
reference. It's tagged as `v0.1` in git history (on `main`) if you need the
original, unmoved layout with working CI/install paths.

It's a working prototype: a phonotactic generator with real per-branch sound
change, an evidence-based lexeme belief store, and cross-branch cognate
hypotheses -- but cognate/hypothesis discovery itself was entirely LLM
judgment from a handful of examples, with hand-picked similarity thresholds
and confidence formulas rather than a principled comparative-method
algorithm. It's superseded by the v2 rewrite (see `docs/SPEC.md` once it
exists), which starts from the actual scientific methodology of historical
linguistics and grounds discovery in deterministic, validated algorithms.

Not maintained going forward. See the root of the repo for the current
implementation.
