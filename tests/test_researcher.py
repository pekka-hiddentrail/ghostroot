# tests/test_researcher.py
from __future__ import annotations

import json

from ghostroot import beliefs
from ghostroot.agents import researcher


def _artifact(aid, branch, text):
    return {
        "id": aid,
        "language": branch,
        "type": "inscription",
        "text": text,
        "metadata": {"discovery": "temple administrative archives"},
    }


def test_first_time_proposal_is_never_treated_as_contradiction(monkeypatch):
    # Regression test: a lexeme with no prior belief was getting
    # evidence_for=0/evidence_against=1 (confidence 0.0) whenever the model
    # answered "supports_existing": false for its very first observation --
    # which is meaningless since there's nothing yet to contradict.
    artifacts = [_artifact("A1", "soruun", "foi")]

    def fake_ask_llm(prompt, **kwargs):
        return json.dumps([
            {
                "form": "foi",
                "branch": "soruun",
                "word_type": "noun: water",
                "meaning": "water",
                "gloss": "water",
                "supports_existing": False,  # model hedges on a fresh guess
            }
        ])

    monkeypatch.setattr(researcher, "ask_llm", fake_ask_llm)

    store = beliefs.empty_store()
    updates = researcher.update_word_beliefs(artifacts=artifacts, beliefs=store)

    entry = store["entries"][beliefs.key_for("soruun", "foi")]
    bucket = entry["interpretations"]["noun: water"]
    assert bucket["evidence_for"] == 1
    assert bucket["evidence_against"] == 0
    assert updates[0]["confidence"] > 0.0


def test_contradiction_of_an_existing_belief_still_counts_against_it(monkeypatch):
    artifacts = [_artifact("A1", "soruun", "foi"), _artifact("A2", "soruun", "foi")]

    store = beliefs.empty_store()
    entry = beliefs.ensure_entry(store, branch="soruun", form="foi", artifact_id="A1")
    beliefs.record_interpretation(entry, word_type="noun: water", meaning="water", supports=True)

    def fake_ask_llm(prompt, **kwargs):
        return json.dumps([
            {
                "form": "foi",
                "branch": "soruun",
                "word_type": "noun: water",
                "meaning": "not water after all",
                "gloss": "",
                "supports_existing": False,  # genuinely contradicts an existing belief
            }
        ])

    monkeypatch.setattr(researcher, "ask_llm", fake_ask_llm)
    researcher.update_word_beliefs(artifacts=artifacts, beliefs=store)

    bucket = entry["interpretations"]["noun: water"]
    assert bucket["evidence_for"] == 1
    assert bucket["evidence_against"] == 1
