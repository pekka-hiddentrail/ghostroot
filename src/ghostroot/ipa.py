# src/ghostroot/ipa.py
from __future__ import annotations

import unicodedata

"""
Standard IPA pulmonic-consonant chart classification (place, manner) --
not derived from PHOIBLE's Hayes-style feature columns, and not a new
panphon dependency. The traditional IPA chart is the single most
established, least-disputable classification in phonetics; using it
directly avoids re-deriving place/manner from either feature system.

Deliberately not exhaustive: rare/complex segments (clicks, non-pulmonic
consonants beyond ejectives, most vowels, tones) return None from
place_and_manner() rather than a guess. Good enough for aggregate
statistical shape (LANGUAGE.md's phoneme-system grounding), not meant to
classify every segment in PHOIBLE's long tail.
"""

_AFFRICATES: dict[str, tuple[str, str]] = {
    "tʃ": ("postalveolar", "affricate"),
    "dʒ": ("postalveolar", "affricate"),
    "ts": ("alveolar", "affricate"),
    "dz": ("alveolar", "affricate"),
}

_CONSONANTS: dict[str, tuple[str, str]] = {
    "p": ("bilabial", "plosive"), "b": ("bilabial", "plosive"),
    "t": ("alveolar", "plosive"), "d": ("alveolar", "plosive"),
    "ʈ": ("retroflex", "plosive"), "ɖ": ("retroflex", "plosive"),
    "c": ("palatal", "plosive"), "ɟ": ("palatal", "plosive"),
    "k": ("velar", "plosive"), "ɡ": ("velar", "plosive"), "g": ("velar", "plosive"),
    "q": ("uvular", "plosive"), "ɢ": ("uvular", "plosive"),
    "ʔ": ("glottal", "plosive"),

    "m": ("bilabial", "nasal"), "ɱ": ("labiodental", "nasal"),
    "n": ("alveolar", "nasal"), "ɳ": ("retroflex", "nasal"),
    "ɲ": ("palatal", "nasal"), "ŋ": ("velar", "nasal"), "ɴ": ("uvular", "nasal"),

    "ʙ": ("bilabial", "trill"), "r": ("alveolar", "trill"), "ʀ": ("uvular", "trill"),

    "ⱱ": ("labiodental", "tap"), "ɾ": ("alveolar", "tap"), "ɽ": ("retroflex", "tap"),

    "ɸ": ("bilabial", "fricative"), "β": ("bilabial", "fricative"),
    "f": ("labiodental", "fricative"), "v": ("labiodental", "fricative"),
    "θ": ("dental", "fricative"), "ð": ("dental", "fricative"),
    "s": ("alveolar", "fricative"), "z": ("alveolar", "fricative"),
    "ʃ": ("postalveolar", "fricative"), "ʒ": ("postalveolar", "fricative"),
    "ʂ": ("retroflex", "fricative"), "ʐ": ("retroflex", "fricative"),
    "ç": ("palatal", "fricative"), "ʝ": ("palatal", "fricative"),
    "x": ("velar", "fricative"), "ɣ": ("velar", "fricative"),
    "χ": ("uvular", "fricative"), "ʁ": ("uvular", "fricative"),
    "ħ": ("pharyngeal", "fricative"), "ʕ": ("pharyngeal", "fricative"),
    "h": ("glottal", "fricative"), "ɦ": ("glottal", "fricative"),

    "ɬ": ("alveolar", "lateral_fricative"), "ɮ": ("alveolar", "lateral_fricative"),

    "ʋ": ("labiodental", "approximant"), "ɹ": ("alveolar", "approximant"),
    "ɻ": ("retroflex", "approximant"), "j": ("palatal", "approximant"),
    "ɰ": ("velar", "approximant"), "w": ("labial-velar", "approximant"),
    "ɥ": ("labial-palatal", "approximant"),

    "l": ("alveolar", "lateral_approximant"), "ɭ": ("retroflex", "lateral_approximant"),
    "ʎ": ("palatal", "lateral_approximant"), "ʟ": ("velar", "lateral_approximant"),
}

# Spacing modifier letters (aspiration ʰ, palatalization ʲ, labialization ʷ,
# ejective ʼ, etc.) commonly appended to a base symbol -- these modify the
# base articulation, they don't change its place/manner category, so
# they're stripped before lookup rather than left to cause a lookup miss.
_MODIFIER_CATEGORY = "Lm"
_COMBINING_MARK_CATEGORY = "Mn"


def base_symbol(ipa: str) -> str:
    """
    Reduces a (possibly diacritic-laden) IPA symbol to its bare base --
    "kʰ" -> "k", "tʲ" -> "t", "n̩" -> "n". NFD decomposition splits
    precomposed characters into base + combining marks first, so a
    diacritic riding on a precomposed character (not just a separate
    modifier letter) is also caught.
    """
    decomposed = unicodedata.normalize("NFD", ipa)
    stripped = "".join(
        ch for ch in decomposed
        if unicodedata.category(ch) not in (_COMBINING_MARK_CATEGORY, _MODIFIER_CATEGORY)
    )
    return unicodedata.normalize("NFC", stripped)


def place_and_manner(ipa: str) -> tuple[str, str] | None:
    """
    (place, manner) for a consonant IPA symbol per the standard IPA chart,
    or None if unrecognized (vowels, tones, clicks, and other segments
    outside the common pulmonic+affricate set -- an unclassified result,
    not an error; PHOIBLE's long tail isn't meant to be fully covered).
    """
    base = base_symbol(ipa)
    if base in _AFFRICATES:
        return _AFFRICATES[base]
    if base in _CONSONANTS:
        return _CONSONANTS[base]
    if base and base[0] in _CONSONANTS:
        return _CONSONANTS[base[0]]
    return None
