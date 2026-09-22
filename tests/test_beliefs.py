# tests/test_beliefs.py
from __future__ import annotations

from ghostroot import beliefs


def test_ensure_entry_creates_and_dedupes_occurrences():
    store = beliefs.empty_store()
    beliefs.ensure_entry(store, branch="soruun", form="Foi", artifact_id="A1")
    beliefs.ensure_entry(store, branch="soruun", form="foi", artifact_id="A1")  # same id, case differs
    beliefs.ensure_entry(store, branch="soruun", form="foi", artifact_id="A2")

    entry = store["entries"][beliefs.key_for("soruun", "foi")]
    assert entry["form"] == "foi"
    assert entry["artifact_ids"] == ["A1", "A2"]


def test_same_surface_form_in_different_branches_are_separate_entries():
    store = beliefs.empty_store()
    beliefs.ensure_entry(store, branch="soruun", form="foi", artifact_id="A1")
    beliefs.ensure_entry(store, branch="kethra", form="foi", artifact_id="A2")
    assert len(store["entries"]) == 2


def test_confidence_of_grows_with_supporting_evidence_and_shrinks_with_contradiction():
    bucket = {"evidence_for": 0, "evidence_against": 0}
    assert beliefs.confidence_of(bucket) == 0.0

    bucket["evidence_for"] = 3
    higher = beliefs.confidence_of(bucket)
    assert higher > 0.0

    bucket["evidence_against"] = 3
    lower = beliefs.confidence_of(bucket)
    assert lower < higher


def test_record_interpretation_supports_updates_meaning_and_gloss():
    store = beliefs.empty_store()
    entry = beliefs.ensure_entry(store, branch="soruun", form="foi", artifact_id="A1")

    beliefs.record_interpretation(entry, word_type="noun: water", meaning="water", gloss="water", supports=True)
    bucket = entry["interpretations"]["noun: water"]
    assert bucket["evidence_for"] == 1
    assert bucket["meaning"] == "water"

    beliefs.record_interpretation(entry, word_type="noun: water", meaning="clear water", gloss="water", supports=True)
    assert bucket["evidence_for"] == 2
    assert bucket["meaning"] == "clear water"


def test_record_interpretation_contradiction_does_not_overwrite_meaning():
    store = beliefs.empty_store()
    entry = beliefs.ensure_entry(store, branch="soruun", form="foi", artifact_id="A1")
    beliefs.record_interpretation(entry, word_type="noun: water", meaning="water", gloss="water", supports=True)

    beliefs.record_interpretation(
        entry, word_type="noun: water", meaning="not water after all", gloss="", supports=False
    )
    bucket = entry["interpretations"]["noun: water"]
    assert bucket["evidence_against"] == 1
    assert bucket["meaning"] == "water"  # unchanged by a contradicting call


def test_top_interpretation_picks_highest_confidence():
    store = beliefs.empty_store()
    entry = beliefs.ensure_entry(store, branch="soruun", form="foi", artifact_id="A1")

    beliefs.record_interpretation(entry, word_type="unknown", meaning="?", supports=True)
    beliefs.record_interpretation(entry, word_type="noun: water", meaning="water", supports=True)
    beliefs.record_interpretation(entry, word_type="noun: water", meaning="water", supports=True)

    top = beliefs.top_interpretation(entry)
    assert top is not None
    word_type, bucket, conf = top
    assert word_type == "noun: water"


def test_top_interpretation_none_when_no_interpretations():
    store = beliefs.empty_store()
    entry = beliefs.ensure_entry(store, branch="soruun", form="foi", artifact_id="A1")
    assert beliefs.top_interpretation(entry) is None


def test_occurrences_for_filters_to_known_artifacts():
    store = beliefs.empty_store()
    entry = beliefs.ensure_entry(store, branch="soruun", form="foi", artifact_id="A1")
    beliefs.ensure_entry(store, branch="soruun", form="foi", artifact_id="A2")

    artifacts_by_id = {"A1": {"id": "A1", "text": "foi"}}  # A2 missing (e.g. deleted)
    occs = beliefs.occurrences_for(entry, artifacts_by_id)
    assert [o["id"] for o in occs] == ["A1"]


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "word_beliefs.json"
    store = beliefs.empty_store()
    entry = beliefs.ensure_entry(store, branch="soruun", form="foi", artifact_id="A1")
    beliefs.record_interpretation(entry, word_type="noun: water", meaning="water", supports=True)

    beliefs.save_beliefs(path, store)
    loaded = beliefs.load_beliefs(path)
    assert loaded == store


def test_load_beliefs_missing_file_returns_empty_store(tmp_path):
    loaded = beliefs.load_beliefs(tmp_path / "does_not_exist.json")
    assert loaded == beliefs.empty_store()


def test_confidence_lookup_scoped_to_branch():
    store = beliefs.empty_store()
    soruun_entry = beliefs.ensure_entry(store, branch="soruun", form="foi", artifact_id="A1")
    beliefs.record_interpretation(soruun_entry, word_type="noun: water", meaning="water", supports=True)
    kethra_entry = beliefs.ensure_entry(store, branch="kethra", form="foi", artifact_id="A2")
    beliefs.record_interpretation(kethra_entry, word_type="particle", meaning="?", supports=True)

    lookup = beliefs.confidence_lookup(store, "soruun")
    assert "foi" in lookup
    assert lookup["foi"] == beliefs.confidence_of(soruun_entry["interpretations"]["noun: water"])
    # kethra's belief about the same surface form must not leak into soruun's lookup
    assert len(lookup) == 1


def test_confidence_lookup_skips_entries_with_no_interpretation():
    store = beliefs.empty_store()
    beliefs.ensure_entry(store, branch="soruun", form="foi", artifact_id="A1")
    assert beliefs.confidence_lookup(store, "soruun") == {}
