# src/ghostroot/protolang.py
from __future__ import annotations

import hashlib
import json
import random
import re
from pathlib import Path
from typing import List, Optional, Tuple

CONSONANTS = list("kptshmnlrwyzgdbfvj")
VOWELS = list("aeiou")
SYLLABLE_SHAPES = ["CV", "CVC", "V"]

DEFAULT_POOL_SIZE = 24

# Candidate sound changes a branch can inherit. Each branch gets a fixed,
# deterministic subset derived from its name, so the same root always
# surfaces the same way within that branch but differently across branches --
# this is what makes cross-branch cognates possible (same root, related forms).
CANDIDATE_RULES: List[Tuple[str, str]] = [
    ("k", "h"),
    ("p", "f"),
    ("t", "d"),
    ("s", "z"),
    ("u", "o"),
    ("i", "e"),
    ("a$", ""),
    ("o$", ""),
    ("n$", "ng"),
    ("g", "gh"),
]


def _syllable(rng: random.Random) -> str:
    shape = rng.choice(SYLLABLE_SHAPES)
    return "".join(rng.choice(CONSONANTS) if ch == "C" else rng.choice(VOWELS) for ch in shape)


def _generate_root(rng: random.Random) -> str:
    n_syllables = rng.choice([2, 2, 2, 3])
    return "".join(_syllable(rng) for _ in range(n_syllables))


def load_or_create_pool(pool_path: Path, size: int = DEFAULT_POOL_SIZE) -> List[str]:
    """
    Loads the persistent proto-root pool, generating and saving it on first use.

    The pool holds bare phonological forms only -- no meaning is attached here.
    Meaning is entirely emergent, produced later by researcher agents
    interpreting how each root behaves across the corpus.
    """
    if pool_path.exists():
        data = json.loads(pool_path.read_text(encoding="utf-8"))
        roots = data.get("roots", [])
        if roots:
            return roots

    rng = random.Random()
    seen = set()
    roots: List[str] = []
    while len(roots) < size:
        root = _generate_root(rng)
        if root not in seen:
            seen.add(root)
            roots.append(root)

    pool_path.parent.mkdir(parents=True, exist_ok=True)
    pool_path.write_text(json.dumps({"roots": roots}, ensure_ascii=False, indent=2), encoding="utf-8")
    return roots


def _branch_rules(branch: str, n_rules: int = 3) -> List[Tuple[str, str]]:
    seed = int(hashlib.sha256(branch.encode("utf-8")).hexdigest(), 16) % (2**32)
    rng = random.Random(seed)
    return rng.sample(CANDIDATE_RULES, k=min(n_rules, len(CANDIDATE_RULES)))


def mutate_for_branch(root: str, branch: str) -> str:
    """Deterministically maps a proto-root to its surface form in `branch`."""
    form = root
    for pattern, repl in _branch_rules(branch):
        mutated = re.sub(pattern, repl, form)
        # Don't let a rule erode a root past recognizability.
        if len(mutated) >= 2:
            form = mutated
    return form


def generate_word(*, branch: str, pool: List[str], rng: Optional[random.Random] = None) -> str:
    rng = rng or random.Random()
    root = rng.choice(pool)
    return mutate_for_branch(root, branch)


def generate_sentence(
    *,
    branch: str,
    pool: List[str],
    max_words: int = 5,
    min_words: int = 2,
    rng: Optional[random.Random] = None,
) -> str:
    rng = rng or random.Random()
    n_words = rng.randint(min_words, max(min_words, max_words))
    words = [generate_word(branch=branch, pool=pool, rng=rng) for _ in range(n_words)]
    return " ".join(words)
