# tests/test_context_researcher.py
from __future__ import annotations

from ghostroot.agents.context_researcher import _extract_word_contexts


def test_extract_word_contexts_uses_discovery_field():
    # Regression test: this used to read metadata['context'], a field that
    # never existed (artifacts store metadata['discovery']), so every word's
    # context silently came back as 'unknown' and the contradiction-detection
    # signal was always empty.
    artifacts = [
        {
            "id": "A1",
            "type": "inscription",
            "text": "foi",
            "language": "soruun",
            "metadata": {"meaning": "to give", "gloss": "give", "confidence": 0.5},
        },
        {
            "id": "A1_S",
            "type": "sentence",
            "text": "foi kara",
            "language": "soruun",
            "metadata": {"discovery": "temple administrative archives"},
        },
    ]

    contexts = _extract_word_contexts(artifacts)

    assert ("soruun", "foi") in contexts
    assert contexts[("soruun", "foi")][0]["context"] == "temple administrative archives"


def test_extract_word_contexts_keys_by_branch_not_just_form():
    # Regression: this used to key by surface form alone, so the same string
    # in two different branches (with two different glosses) would silently
    # conflate into one entry -- one branch's gloss overwriting the other's.
    artifacts = [
        {
            "id": "A1", "type": "inscription", "text": "bame", "language": "ilvath",
            "metadata": {"meaning": "an office", "gloss": "office", "confidence": 0.5},
        },
        {
            "id": "A2", "type": "inscription", "text": "bame", "language": "soruun",
            "metadata": {"meaning": "a totally different thing", "gloss": "other", "confidence": 0.5},
        },
        {
            "id": "A1_S", "type": "sentence", "text": "bame kara", "language": "ilvath",
            "metadata": {"discovery": "market regulation offices"},
        },
        {
            "id": "A2_S", "type": "sentence", "text": "bame kara", "language": "soruun",
            "metadata": {"discovery": "temple archives"},
        },
    ]

    contexts = _extract_word_contexts(artifacts)

    assert len(contexts) == 2
    assert contexts[("ilvath", "bame")][0]["word_gloss"]["meaning"] == "an office"
    assert contexts[("soruun", "bame")][0]["word_gloss"]["meaning"] == "a totally different thing"


def test_extract_word_contexts_ignores_ungossed_words():
    artifacts = [
        {"id": "A1", "type": "inscription", "text": "foi", "language": "soruun", "metadata": {}},  # no meaning set
        {
            "id": "A1_S",
            "type": "sentence",
            "text": "foi kara",
            "language": "soruun",
            "metadata": {"discovery": "temple administrative archives"},
        },
    ]

    contexts = _extract_word_contexts(artifacts)
    assert contexts == {}
