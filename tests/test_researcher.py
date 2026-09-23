# tests/test_researcher.py
from __future__ import annotations

import json

from ghostroot import beliefs
from ghostroot import proto_hypotheses as hyp
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


def _fake_corpus_report(hypotheses_json):
    def fake_ask_llm(prompt, **kwargs):
        return (
            "## Cognate Sets\n_None this pass._\n\n"
            "## Proto-root Hypotheses\n_None this pass._\n\n"
            "## Open Questions\n_None this pass._\n\n"
            f"```json\n{json.dumps(hypotheses_json)}\n```"
        )
    return fake_ask_llm


def test_analyze_corpus_persists_new_hypothesis_into_the_store(monkeypatch):
    monkeypatch.setattr(
        researcher, "ask_llm",
        _fake_corpus_report([
            {"root": "*wu", "gloss": "boundary", "meaning": "a limit or edge",
             "reasoning": "repeated form", "confidence": "low"},
        ]),
    )

    store = hyp.empty_store()
    note = researcher.analyze_corpus(
        entry_id="R1", artifacts=[], proto_hypotheses=store,
    )

    assert store["hypotheses"]["wu"]["confidence"] == "low"
    assert "*wu*" in note["summary"]
    assert "## Summary (all hypotheses tracked so far)" in note["summary"]


def test_analyze_corpus_carries_forward_a_hypothesis_not_mentioned_this_pass(monkeypatch):
    # Regression for: a hypothesis raised in an earlier pass used to vanish
    # from the report the moment a later pass's freeform output didn't
    # happen to re-mention it, even though nothing ever refuted it.
    store = hyp.empty_store()
    hyp.upsert_hypothesis(
        store, root="dollar", gloss="money", meaning="unit of exchange",
        reasoning="seen in tax contexts", confidence="med", pass_id="R1",
    )

    monkeypatch.setattr(researcher, "ask_llm", _fake_corpus_report([]))  # this pass proposes nothing new

    note = researcher.analyze_corpus(
        entry_id="R2", artifacts=[], proto_hypotheses=store,
    )

    assert "**dollar**" in note["summary"]  # still shown in the persistent summary


def test_analyze_corpus_shows_confidence_arrow_when_a_hypothesis_is_revised(monkeypatch):
    store = hyp.empty_store()
    hyp.upsert_hypothesis(
        store, root="dollar", gloss="money", meaning="unit of exchange",
        reasoning="seen in tax contexts", confidence="low", pass_id="R1",
    )

    monkeypatch.setattr(
        researcher, "ask_llm",
        _fake_corpus_report([
            {"root": "dollar", "gloss": "money", "meaning": "unit of exchange",
             "reasoning": "reinforced across three branches", "confidence": "high",
             "branches": ["ilvath", "soruun", "kethra"]},
        ]),
    )

    note = researcher.analyze_corpus(
        entry_id="R2", artifacts=[], proto_hypotheses=store,
    )

    assert "low → high" in note["summary"]


def test_analyze_corpus_caps_confidence_when_only_one_branch_attests_it(monkeypatch):
    # A hypothesis backed by a single occurrence in a single branch shouldn't
    # be reportable as "high" confidence just because the model phrased it
    # assertively -- confidence must be earned by cross-branch attestation.
    monkeypatch.setattr(
        researcher, "ask_llm",
        _fake_corpus_report([
            {"root": "*wu", "gloss": "boundary", "meaning": "a limit or edge",
             "reasoning": "single occurrence", "confidence": "high",
             "branches": ["ilvath"]},
        ]),
    )

    store = hyp.empty_store()
    researcher.analyze_corpus(
        entry_id="R1", artifacts=[], proto_hypotheses=store,
    )

    assert store["hypotheses"]["wu"]["confidence"] == "low"


def test_disagreement_with_a_different_word_type_penalizes_the_old_belief_not_the_new_one(monkeypatch):
    # Regression: this was observed live -- ilvath:dollar's "noun" bucket sat
    # frozen at evidence_for=1/evidence_against=0 forever while "particle"
    # (proposed instead, with supports_existing=False, across several later
    # passes) got shot down to evidence_for=0/evidence_against=5. The old
    # code recorded the disagreement against the NEW candidate's own bucket
    # instead of the OLD belief actually being contradicted -- backwards.
    artifacts = [_artifact("A1", "ilvath", "dollar")]

    store = beliefs.empty_store()
    entry = beliefs.ensure_entry(store, branch="ilvath", form="dollar", artifact_id="A1")
    beliefs.record_interpretation(entry, word_type="noun", meaning="a prayer fragment", supports=True)

    def fake_ask_llm(prompt, **kwargs):
        return json.dumps([
            {
                "form": "dollar",
                "branch": "ilvath",
                "word_type": "particle",
                "meaning": "a discourse particle of uncertain function",
                "gloss": "particle",
                "supports_existing": False,  # disagrees with the current "noun" belief
            }
        ])

    monkeypatch.setattr(researcher, "ask_llm", fake_ask_llm)
    researcher.update_word_beliefs(artifacts=artifacts, beliefs=store)

    noun_bucket = entry["interpretations"]["noun"]
    particle_bucket = entry["interpretations"]["particle"]
    assert noun_bucket["evidence_against"] == 1  # the OLD belief takes the hit
    assert particle_bucket["evidence_for"] == 1  # the NEW candidate gets real support
    assert particle_bucket["evidence_against"] == 0


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
