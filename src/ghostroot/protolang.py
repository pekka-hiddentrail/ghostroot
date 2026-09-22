# src/ghostroot/protolang.py
from __future__ import annotations

import hashlib
import json
import random
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CONSONANTS = list("kptshmnlrwyzgdbfvj")
VOWELS = list("aeiou")
SYLLABLE_SHAPES = ["CV", "CVC", "V"]

DEFAULT_POOL_SIZE = 24
STRUCTURAL_FRACTION = 0.2  # share of roots that behave like function words
STRUCTURAL_WEIGHT = 3  # how much more often a structural root gets picked
SAME_DOMAIN_PROB = 0.8  # how often a content root's discovery matches its domain
FEEDBACK_CONFIDENCE_BOOST = 4.0  # weight multiplier at confidence=1.0 for the belief feedback loop

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

# Discovery contexts grouped into coarse semantic domains. Content roots are
# hidden-tied to one domain (see load_or_create_pool); structural roots ignore
# domain entirely and draw from all of them uniformly -- the same distinction
# real function words vs. content words show in a corpus.
DOMAIN_DISCOVERIES: Dict[str, List[str]] = {
    "trade": [
        "trade receipt scratched on wood",
        "merchant accounting rooms",
        "warehouse inventory stores",
        "harbor customs offices",
        "market regulation offices",
        "river transport offices",
    ],
    "religious": [
        "short prayer fragment",
        "temple administrative archives",
        "priesthood ritual storerooms",
        "oracle consultation chambers",
        "omen interpretation libraries",
        "temple treasury vaults",
    ],
    "administrative": [
        "palace record rooms",
        "royal chancellery archives",
        "provincial governor residences",
        "law court record rooms",
        "taxation registry offices",
        "census enumeration records",
        "diplomatic correspondence caches",
        "treaty tablet deposits",
    ],
    "funerary": [
        "tomb offering label",
        "burial chamber deposits",
        "cemetery grave goods",
        "scribal school tablets",
    ],
    "military": [
        "boundary marker inscription",
        "military camp headquarters",
        "frontier fort garrisons",
        "city gate offices",
        "city wall guardhouses",
        "road checkpoint stations",
    ],
    "domestic": [
        "graffiti near a dock",
        "maker's mark on a tool",
        "private household archives",
        "healer practice archives",
        "astronomical observation records",
    ],
    "agricultural": [
        "canal maintenance offices",
        "irrigation control stations",
        "agricultural estate offices",
        "workshop accounting archives",
        "ration distribution offices",
        "labor assignment records",
    ],
}

ALL_DISCOVERIES: List[str] = [d for group in DOMAIN_DISCOVERIES.values() for d in group]
DOMAINS: List[str] = list(DOMAIN_DISCOVERIES.keys())


def _syllable(rng: random.Random) -> str:
    shape = rng.choice(SYLLABLE_SHAPES)
    return "".join(rng.choice(CONSONANTS) if ch == "C" else rng.choice(VOWELS) for ch in shape)


def _generate_root(rng: random.Random) -> str:
    n_syllables = rng.choice([2, 2, 2, 3])
    return "".join(_syllable(rng) for _ in range(n_syllables))


def load_or_create_pool(pool_path: Path, size: int = DEFAULT_POOL_SIZE) -> List[Dict[str, Any]]:
    """
    Loads the persistent proto-root pool, generating and saving it on first use.

    Each root carries a hidden `role` ("structural" or "content") and, for
    content roots, a hidden `domain`. Neither is exposed to the researcher --
    they only shape *how* words get generated and which discovery contexts
    they tend to appear in. Meaning itself is never attached here; it's
    entirely emergent, produced later by researcher agents interpreting how
    each root behaves across the corpus.
    """
    if pool_path.exists():
        data = json.loads(pool_path.read_text(encoding="utf-8"))
        roots = data.get("roots", [])
        if roots and isinstance(roots[0], dict):
            return roots
        # Legacy (pre-role) pool format -- regenerate with the new schema.

    rng = random.Random()
    seen = set()
    forms: List[str] = []
    while len(forms) < size:
        root = _generate_root(rng)
        if root not in seen:
            seen.add(root)
            forms.append(root)

    roots = []
    for i, form in enumerate(forms):
        if i < max(1, round(size * STRUCTURAL_FRACTION)):
            roots.append({"form": form, "role": "structural", "domain": None})
        else:
            roots.append({"form": form, "role": "content", "domain": rng.choice(DOMAINS)})
    rng.shuffle(roots)

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


def choose_root(
    pool: List[Dict[str, Any]],
    rng: Optional[random.Random] = None,
    *,
    branch: Optional[str] = None,
    confidence_lookup: Optional[Dict[str, float]] = None,
    confidence_boost: float = FEEDBACK_CONFIDENCE_BOOST,
) -> Dict[str, Any]:
    """
    Picks a root, weighting structural roots higher -- real function words
    are used far more often than any single content word.

    If `confidence_lookup` (branch -> surface form -> belief confidence, see
    beliefs.confidence_lookup) and `branch` are given, roots the researcher
    has already converged on get reinforced further. This is the feedback
    loop: established vocabulary keeps getting reused instead of the corpus
    drifting through equally-likely fresh nonsense forever.
    """
    rng = rng or random.Random()
    weights = []
    for r in pool:
        w = float(STRUCTURAL_WEIGHT if r["role"] == "structural" else 1)
        if confidence_lookup and branch is not None:
            surface = mutate_for_branch(r["form"], branch)
            conf = confidence_lookup.get(surface, 0.0)
            w *= 1 + confidence_boost * conf
        weights.append(w)
    return rng.choices(pool, weights=weights, k=1)[0]


def choose_discovery(root_entry: Dict[str, Any], rng: Optional[random.Random] = None) -> str:
    """
    Structural roots ignore domain and scatter across all contexts uniformly.
    Content roots mostly (not always) surface in their hidden domain, keeping
    some realistic noise rather than a perfect tell.
    """
    rng = rng or random.Random()
    if root_entry["role"] == "structural" or not root_entry.get("domain"):
        return rng.choice(ALL_DISCOVERIES)
    if rng.random() < SAME_DOMAIN_PROB:
        return rng.choice(DOMAIN_DISCOVERIES[root_entry["domain"]])
    return rng.choice(ALL_DISCOVERIES)


def generate_word(
    *,
    branch: str,
    pool: List[Dict[str, Any]],
    rng: Optional[random.Random] = None,
    confidence_lookup: Optional[Dict[str, float]] = None,
) -> str:
    rng = rng or random.Random()
    root_entry = choose_root(pool, rng, branch=branch, confidence_lookup=confidence_lookup)
    return mutate_for_branch(root_entry["form"], branch)


def generate_sentence(
    *,
    branch: str,
    pool: List[Dict[str, Any]],
    max_words: int = 5,
    min_words: int = 2,
    rng: Optional[random.Random] = None,
    confidence_lookup: Optional[Dict[str, float]] = None,
) -> str:
    rng = rng or random.Random()
    n_words = rng.randint(min_words, max(min_words, max_words))
    words = [
        generate_word(branch=branch, pool=pool, rng=rng, confidence_lookup=confidence_lookup)
        for _ in range(n_words)
    ]
    return " ".join(words)
