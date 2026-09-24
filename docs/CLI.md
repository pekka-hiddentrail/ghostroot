# CLI

Why a real CLI, not ad-hoc runs: seeded determinism only means anything if
a run is exactly re-invokable, and the interactive mutation prompt below
can't work through one-shot script execution.

## Commands

- **`generate N`** — bootstrap N new finds into the current world's corpus
  (world seed + corpus seed already fixed at world creation, read from
  `world_manifest`).
- **`analyze [--max-rounds R]`** — runs the specialist round-robin
  (`ARCHITECTURE.md` §15) to convergence or `R` rounds, whichever first.
  May write a report afterward (format/contents TBD, not designed yet).
- **`gloss`** — the one LLM step, bounded, runs after `analyze` converges.
- **`advance-era [--mutation N]`** — triggers diachronic mutation. Reads
  `world_manifest` from SQLite (world info, seeds), applies the mutations
  due for the next date-band.

## Mutation soft-gate

Default: pause and ask at 500 sentences since the last mutation. `[Y]`
launches the mutation; `[N]` asks for a new wait interval (another 500, or
a different number) before asking again. `--mutation N` overrides the
*first* prompt's threshold (e.g. `--mutation 80` for fast local testing) —
subsequent thresholds are still whatever's chosen at each `[N]` prompt.

## Mutation seed derivation

One `mutation_seed` expands into a sub-seed per affected subsystem (sound
change, syllable structure, grammar/categories, ...), so they don't all
replay the same pseudo-random sequence, plus a per-round term so repeated
`advance-era` calls don't reuse the same sub-seed family:

```
TARGET_OFFSET = {"sound": 1, "syllable": 2, "grammar": 3, ...}
ROUND_STRIDE = 1000  # large enough that round_number and TARGET_OFFSET never collide

sub_seed(mutation_seed, target, round_number) =
    mutation_seed + TARGET_OFFSET[target] + round_number * ROUND_STRIDE
```

Plain integer arithmetic, not `hash()` — Python's built-in `hash()` on
strings/tuples is randomized per process (`PYTHONHASHSEED`) unless
disabled, which would silently break reproducibility between runs. Fully
deterministic: same `mutation_seed` and round number always derive the
same sub-seed, every time, on any machine.
