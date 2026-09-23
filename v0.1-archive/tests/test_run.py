# tests/test_run.py
from __future__ import annotations

from ghostroot import beliefs
from ghostroot.run import _apply_context_contradictions, _attested_forms, _belief_snapshot, _pass_outcome


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


def test_pass_outcome_confirmed_on_brand_new_interpretation():
    store = _store_with({"soruun:foi": ("noun: water", "water", 1, 0)})
    before = {}  # nothing existed yet
    outcome = _pass_outcome(before, store)
    assert outcome == "confirmed"


def test_pass_outcome_confirmed_on_reinforced_belief():
    store = _store_with({"soruun:foi": ("noun: water", "water", 1, 0)})
    before = _belief_snapshot(store)
    beliefs.record_interpretation(
        store["entries"]["soruun:foi"], word_type="noun: water", meaning="water", supports=True
    )
    outcome = _pass_outcome(before, store)
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
    outcome = _pass_outcome(before, store)
    assert outcome == "contradicted"


def test_pass_outcome_contradicted_when_confidence_drops():
    store = _store_with({"soruun:foi": ("noun: water", "water", 2, 0)})
    before = _belief_snapshot(store)
    beliefs.record_interpretation(
        store["entries"]["soruun:foi"], word_type="noun: water", meaning="water", supports=False
    )
    outcome = _pass_outcome(before, store)
    assert outcome == "contradicted"


def test_pass_outcome_none_when_nothing_changed():
    store = _store_with({"soruun:foi": ("noun: water", "water", 1, 0)})
    before = _belief_snapshot(store)
    outcome = _pass_outcome(before, store)
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
    outcome = _pass_outcome(before, store)
    assert outcome == "confirmed"


def test_pass_outcome_counts_a_context_contradiction():
    store = _store_with({})
    before = _belief_snapshot(store)
    outcome = _pass_outcome(before, store, contradictions_found=1)
    assert outcome == "contradicted"


# --- _apply_context_contradictions: the context-check -> belief-store feedback loop ---

def test_apply_context_contradictions_lowers_confidence_of_the_current_top():
    store = _store_with({"soruun:waka": ("verb: to cover", "to cover something", 3, 0)})
    before_conf = beliefs.top_interpretation(store["entries"]["soruun:waka"])[2]

    updates = _apply_context_contradictions(
        store, [{"branch": "soruun", "form": "waka", "note": "seen in unrelated contexts"}],
    )

    after_conf = beliefs.top_interpretation(store["entries"]["soruun:waka"])[2]
    assert after_conf < before_conf
    assert updates and updates[0]["confidence"] == after_conf


def test_apply_context_contradictions_ignores_unknown_lexemes():
    store = beliefs.empty_store()
    updates = _apply_context_contradictions(
        store, [{"branch": "soruun", "form": "nonexistent", "note": "?"}],
    )
    assert updates == []


def test_apply_context_contradictions_ignores_lexemes_with_no_interpretation_yet():
    store = beliefs.empty_store()
    beliefs.ensure_entry(store, branch="soruun", form="waka", artifact_id="A1")  # no interpretation recorded
    updates = _apply_context_contradictions(
        store, [{"branch": "soruun", "form": "waka", "note": "?"}],
    )
    assert updates == []


def test_attested_forms_only_counts_inscriptions_in_the_given_branch():
    artifacts = [
        {"type": "inscription", "language": "ilvath", "text": "Kal"},
        {"type": "inscription", "language": "soruun", "text": "zeb"},
        {"type": "sentence", "language": "ilvath", "text": "kal zeb"},  # sentences don't count
    ]
    assert _attested_forms(artifacts, "ilvath") == {"kal"}  # case-folded
    assert _attested_forms(artifacts, "soruun") == {"zeb"}
    assert _attested_forms(artifacts, "kethra") == set()
