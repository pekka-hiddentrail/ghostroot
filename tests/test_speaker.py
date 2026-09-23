# tests/test_speaker.py
from __future__ import annotations

import json

from ghostroot import protolang
from ghostroot.agents.speaker import generate_artifact


def _write_pool(path, roots):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"roots": roots}), encoding="utf-8")


def test_reinforcement_only_produces_a_single_sentence_artifact(tmp_path):
    pool_path = tmp_path / "proto_lexicon.json"
    _write_pool(pool_path, [
        {"form": "kal", "role": "content", "domain": "trade", "pos": "noun"},
        {"form": "tol", "role": "structural", "domain": None, "pos": "particle"},
    ])

    artifacts = generate_artifact(
        backend="groq", model="x", branch="ilvath", artifact_id="A1",
        word_generator="phonotactic", proto_lexicon_path=pool_path,
        reinforcement_only=True, attested_forms={"kal"},
    )

    assert len(artifacts) == 1
    assert artifacts[0]["type"] == "sentence"
    assert artifacts[0]["id"] == "A1_S"


def test_reinforcement_only_restricts_vocabulary_to_attested_forms(tmp_path):
    pool_path = tmp_path / "proto_lexicon.json"
    _write_pool(pool_path, [
        {"form": "kal", "role": "content", "domain": "trade", "pos": "noun"},
        {"form": "zeb", "role": "content", "domain": "military", "pos": "verb"},
    ])

    attested = {protolang.mutate_for_branch("kal", "ilvath")}

    artifacts = generate_artifact(
        backend="groq", model="x", branch="ilvath", artifact_id="A1",
        word_generator="phonotactic", proto_lexicon_path=pool_path,
        min_words=6, max_words=6,
        reinforcement_only=True, attested_forms=attested,
    )

    words = artifacts[0]["text"].split()
    assert words  # sentence was actually generated
    assert all(w in attested for w in words)


def test_reinforcement_only_falls_back_to_full_pool_when_nothing_attested(tmp_path):
    pool_path = tmp_path / "proto_lexicon.json"
    _write_pool(pool_path, [
        {"form": "kal", "role": "content", "domain": "trade", "pos": "noun"},
    ])

    # Empty attested_forms (e.g. the very first bootstrap batch, nothing
    # spoken yet) shouldn't crash or produce an empty sentence -- fall back
    # to generating from the full pool instead.
    artifacts = generate_artifact(
        backend="groq", model="x", branch="ilvath", artifact_id="A1",
        word_generator="phonotactic", proto_lexicon_path=pool_path,
        reinforcement_only=True, attested_forms=set(),
    )

    assert artifacts[0]["text"].strip() != ""


def test_min_words_and_max_words_are_threaded_through_to_sentence_length(tmp_path):
    pool_path = tmp_path / "proto_lexicon.json"
    _write_pool(pool_path, [
        {"form": "kal", "role": "content", "domain": "trade", "pos": "noun"},
        {"form": "tol", "role": "structural", "domain": None, "pos": "particle"},
    ])

    artifacts = generate_artifact(
        backend="groq", model="x", branch="ilvath", artifact_id="A1",
        word_generator="phonotactic", proto_lexicon_path=pool_path,
        min_words=7, max_words=7,
    )

    sentence = artifacts[1]["text"]
    assert len(sentence.split()) == 7
