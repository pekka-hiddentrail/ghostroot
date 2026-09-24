# tests/test_ipa.py
from __future__ import annotations

from ghostroot.ipa import base_symbol, place_and_manner


def test_base_symbol_strips_aspiration():
    assert base_symbol("kʰ") == "k"


def test_base_symbol_strips_palatalization():
    assert base_symbol("tʲ") == "t"


def test_base_symbol_strips_combining_diacritic_on_precomposed_char():
    # n + combining syllabic mark (below), NFD-decomposable
    assert base_symbol("n̩") == "n"


def test_base_symbol_strips_ejective_marker():
    assert base_symbol("kʼ") == "k"


def test_base_symbol_leaves_plain_symbol_unchanged():
    assert base_symbol("k") == "k"


def test_place_and_manner_plosives():
    assert place_and_manner("p") == ("bilabial", "plosive")
    assert place_and_manner("t") == ("alveolar", "plosive")
    assert place_and_manner("k") == ("velar", "plosive")
    assert place_and_manner("ʔ") == ("glottal", "plosive")


def test_place_and_manner_fricatives():
    assert place_and_manner("s") == ("alveolar", "fricative")
    assert place_and_manner("h") == ("glottal", "fricative")


def test_place_and_manner_nasals():
    assert place_and_manner("m") == ("bilabial", "nasal")
    assert place_and_manner("ŋ") == ("velar", "nasal")


def test_place_and_manner_handles_diacritics():
    assert place_and_manner("kʰ") == ("velar", "plosive")
    assert place_and_manner("tʲ") == ("alveolar", "plosive")


def test_place_and_manner_affricate_ligatures():
    assert place_and_manner("tʃ") == ("postalveolar", "affricate")
    assert place_and_manner("dʒ") == ("postalveolar", "affricate")


def test_place_and_manner_unrecognized_segment_returns_none():
    assert place_and_manner("a") is None  # vowel
    assert place_and_manner("ǀ") is None  # click
