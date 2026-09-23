# tests/test_proto_hypotheses.py
from __future__ import annotations

from ghostroot import proto_hypotheses as hyp


def test_upsert_new_hypothesis_has_no_prior_confidence():
    store = hyp.empty_store()
    entry = hyp.upsert_hypothesis(
        store, root="*wu", gloss="boundary", meaning="a limit or edge",
        reasoning="repeated form", pass_id="R1", branches=["ilvath"],
    )
    assert entry["prior_confidence"] is None
    assert entry["confidence"] == 0.25  # 1 / (1 + 3)
    assert entry["first_seen_pass"] == "R1"


def test_upsert_reaffirming_same_branch_count_clears_prior():
    store = hyp.empty_store()
    hyp.upsert_hypothesis(
        store, root="*wu", gloss="boundary", meaning="a limit",
        reasoning="r1", pass_id="R1", branches=["ilvath"],
    )
    entry = hyp.upsert_hypothesis(
        store, root="*wu", gloss="boundary", meaning="a limit",
        reasoning="r2", pass_id="R2", branches=["ilvath"],
    )
    assert entry["prior_confidence"] is None
    assert entry["first_seen_pass"] == "R1"  # preserved across updates


def test_upsert_new_branch_attestation_raises_confidence_and_sets_prior():
    store = hyp.empty_store()
    hyp.upsert_hypothesis(
        store, root="*wu", gloss="boundary", meaning="a limit",
        reasoning="r1", pass_id="R1", branches=["ilvath"],
    )
    entry = hyp.upsert_hypothesis(
        store, root="*wu", gloss="boundary", meaning="a limit",
        reasoning="r2", pass_id="R2", branches=["ilvath", "soruun", "kethra"],
    )
    assert entry["prior_confidence"] == 0.25
    assert entry["confidence"] == 0.5  # 3 / (3 + 3)


def test_normalize_root_collapses_notational_variants():
    store = hyp.empty_store()
    hyp.upsert_hypothesis(
        store, root="*Wu", gloss="boundary", meaning="a limit",
        reasoning="r1", pass_id="R1", branches=["ilvath"],
    )
    entry = hyp.upsert_hypothesis(
        store, root="wu", gloss="boundary (revised)", meaning="an edge",
        reasoning="r2", pass_id="R2", branches=["ilvath", "soruun"],
    )
    assert len(store["hypotheses"]) == 1
    assert entry["prior_confidence"] == 0.25


def test_confidence_display_shows_percentage_arrow_only_when_changed():
    store = hyp.empty_store()
    hyp.upsert_hypothesis(
        store, root="dollar", gloss="money", meaning="unit of exchange",
        reasoning="r1", pass_id="R1", branches=["ilvath", "soruun"],
    )
    unchanged = hyp.upsert_hypothesis(
        store, root="dollar", gloss="money", meaning="unit of exchange",
        reasoning="r2", pass_id="R2", branches=["ilvath", "soruun"],
    )
    assert hyp.confidence_display(unchanged) == "40%"

    changed = hyp.upsert_hypothesis(
        store, root="dollar", gloss="money", meaning="unit of exchange",
        reasoning="r3", pass_id="R3", branches=["ilvath", "soruun", "kethra"],
    )
    assert hyp.confidence_display(changed) == "40% → 50%"


def test_render_summary_lists_all_tracked_hypotheses_sorted_by_confidence():
    store = hyp.empty_store()
    hyp.upsert_hypothesis(
        store, root="a", gloss="", meaning="low one",
        reasoning="", pass_id="R1", branches=["ilvath"],
    )
    hyp.upsert_hypothesis(
        store, root="b", gloss="", meaning="high one",
        reasoning="", pass_id="R1", branches=["ilvath", "soruun", "kethra"],
    )
    summary = hyp.render_summary(store)
    assert summary.index("**b**") < summary.index("**a**")


def test_render_summary_empty_store():
    assert hyp.render_summary(hyp.empty_store()) == "_No proto-root hypotheses tracked yet._"


def test_save_and_load_round_trip(tmp_path):
    path = tmp_path / "proto_hypotheses.json"
    store = hyp.empty_store()
    hyp.upsert_hypothesis(
        store, root="dollar", gloss="money", meaning="unit of exchange",
        reasoning="repeated in tax contexts", pass_id="R1",
        branches=["ilvath", "soruun"],
    )
    hyp.save_hypotheses(path, store)

    loaded = hyp.load_hypotheses(path)
    assert loaded["hypotheses"]["dollar"]["meaning"] == "unit of exchange"


def test_load_hypotheses_missing_file_returns_empty_store(tmp_path):
    assert hyp.load_hypotheses(tmp_path / "missing.json") == hyp.empty_store()


def test_load_hypotheses_invalid_json_returns_empty_store(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    assert hyp.load_hypotheses(path) == hyp.empty_store()


# --- n=1 overconfidence guard: confidence is computed from attested branch count ---

def test_confidence_is_low_when_only_one_branch_attests_it():
    store = hyp.empty_store()
    entry = hyp.upsert_hypothesis(
        store, root="dollar", gloss="money", meaning="unit of exchange",
        reasoning="single occurrence", pass_id="R1", branches=["ilvath"],
    )
    assert entry["confidence"] == 0.25


def test_confidence_grows_with_more_branches():
    store = hyp.empty_store()
    entry = hyp.upsert_hypothesis(
        store, root="dollar", gloss="money", meaning="unit of exchange",
        reasoning="three branches", pass_id="R1",
        branches=["ilvath", "soruun", "kethra"],
    )
    assert entry["confidence"] == 0.5


def test_confidence_deduplicates_repeated_branch_names():
    store = hyp.empty_store()
    entry = hyp.upsert_hypothesis(
        store, root="dollar", gloss="money", meaning="unit of exchange",
        reasoning="same branch listed twice", pass_id="R1",
        branches=["ilvath", "ilvath"],
    )
    assert entry["confidence"] == 0.25  # still counts as 1 distinct branch


def test_missing_branches_defaults_to_zero_confidence():
    store = hyp.empty_store()
    entry = hyp.upsert_hypothesis(
        store, root="dollar", gloss="money", meaning="unit of exchange",
        reasoning="no branches reported", pass_id="R1",
    )
    assert entry["confidence"] == 0.0
