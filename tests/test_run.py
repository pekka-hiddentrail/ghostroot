# tests/test_run.py
from __future__ import annotations

from ghostroot import beliefs
from ghostroot.run import _belief_snapshot, _pass_outcome


def _store_with(entries):
    """entries: dict of key -> (word_type, meaning, evidence_for, evidence_against)"""
    store = beliefs.empty_store()
    for key, (word_type, meaning, evidence_for, evidence_against) in entries.items():
        branch, form = key.split(":", 1)
        entry = beliefs.ensure_entry(store, branch=branch, form=form, artifact_id="A1")
        for _ in range(evidence_for):
            beliefs.record_interpretation(entry, word_type=word_type, meaning=meaning, supports=True)
        for _ in range(evidence_against):
            beliefs.record_interpretation(entry, word_type=word_type, meaning=meaning, supports=False)
    return store


def _empty_context_note():
    return {"summary": "No issues found."}


def test_pass_outcome_confirmed_on_brand_new_interpretation():
    store = _store_with({"soruun:foi": ("noun: water", "water", 1, 0)})
    before = {}  # nothing existed yet
    outcome = _pass_outcome(before, store, new_questions=[], updated_questions=[], context_note=_empty_context_note())
    assert outcome == "confirmed"


def test_pass_outcome_confirmed_on_reinforced_belief():
    store = _store_with({"soruun:foi": ("noun: water", "water", 1, 0)})
    before = _belief_snapshot(store)
    beliefs.record_interpretation(
        store["entries"]["soruun:foi"], word_type="noun: water", meaning="water", supports=True
    )
    outcome = _pass_outcome(before, store, new_questions=[], updated_questions=[], context_note=_empty_context_note())
    assert outcome == "confirmed"


def test_pass_outcome_contradicted_when_word_type_flips():
    store = _store_with({"soruun:foi": ("noun: water", "water", 1, 0)})
    before = _belief_snapshot(store)
    # Give the competing interpretation enough evidence to actually overtake
    # the existing top (a tie wouldn't dethrone it, and that's correct).
    for _ in range(3):
        beliefs.record_interpretation(
            store["entries"]["soruun:foi"], word_type="particle", meaning="?", supports=True
        )
    outcome = _pass_outcome(before, store, new_questions=[], updated_questions=[], context_note=_empty_context_note())
    assert outcome == "contradicted"


def test_pass_outcome_contradicted_when_confidence_drops():
    store = _store_with({"soruun:foi": ("noun: water", "water", 2, 0)})
    before = _belief_snapshot(store)
    beliefs.record_interpretation(
        store["entries"]["soruun:foi"], word_type="noun: water", meaning="water", supports=False
    )
    outcome = _pass_outcome(before, store, new_questions=[], updated_questions=[], context_note=_empty_context_note())
    assert outcome == "contradicted"


def test_pass_outcome_none_when_nothing_changed():
    store = _store_with({"soruun:foi": ("noun: water", "water", 1, 0)})
    before = _belief_snapshot(store)
    outcome = _pass_outcome(before, store, new_questions=[], updated_questions=[], context_note=_empty_context_note())
    assert outcome == "none"


def test_pass_outcome_confirmed_takes_priority_over_contradiction():
    store = _store_with({
        "soruun:foi": ("noun: water", "water", 1, 0),
        "kethra:bar": ("noun: fire", "fire", 1, 0),
    })
    before = _belief_snapshot(store)
    # One lexeme reinforced (confirmed), another flips (contradicted) -- confirmed wins.
    beliefs.record_interpretation(
        store["entries"]["soruun:foi"], word_type="noun: water", meaning="water", supports=True
    )
    beliefs.record_interpretation(
        store["entries"]["kethra:bar"], word_type="verb", meaning="?", supports=True
    )
    outcome = _pass_outcome(before, store, new_questions=[], updated_questions=[], context_note=_empty_context_note())
    assert outcome == "confirmed"


def test_pass_outcome_new_question_counts_as_confirmed():
    store = _store_with({})
    before = _belief_snapshot(store)
    outcome = _pass_outcome(
        before, store, new_questions=[{"question": "?"}], updated_questions=[], context_note=_empty_context_note()
    )
    assert outcome == "confirmed"


def test_pass_outcome_updated_question_counts_as_contradicted():
    store = _store_with({})
    before = _belief_snapshot(store)
    outcome = _pass_outcome(
        before, store, new_questions=[], updated_questions=[{"question": "?"}], context_note=_empty_context_note()
    )
    assert outcome == "contradicted"


def test_pass_outcome_contradiction_keyword_in_context_note_counts():
    store = _store_with({})
    before = _belief_snapshot(store)
    outcome = _pass_outcome(
        before, store, new_questions=[], updated_questions=[],
        context_note={"summary": "This gloss appears to contradict its context."},
    )
    assert outcome == "contradicted"
