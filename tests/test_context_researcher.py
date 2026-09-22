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
            "metadata": {"meaning": "to give", "gloss": "give", "confidence": 0.5},
        },
        {
            "id": "A1_S",
            "type": "sentence",
            "text": "foi kara",
            "metadata": {"discovery": "temple administrative archives"},
        },
    ]

    contexts = _extract_word_contexts(artifacts)

    assert "foi" in contexts
    assert contexts["foi"][0]["context"] == "temple administrative archives"


def test_extract_word_contexts_ignores_ungossed_words():
    artifacts = [
        {"id": "A1", "type": "inscription", "text": "foi", "metadata": {}},  # no meaning set
        {
            "id": "A1_S",
            "type": "sentence",
            "text": "foi kara",
            "metadata": {"discovery": "temple administrative archives"},
        },
    ]

    contexts = _extract_word_contexts(artifacts)
    assert contexts == {}
