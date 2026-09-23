# tests/test_protolang.py
from __future__ import annotations

import collections
import json
import random

from ghostroot import protolang


def test_load_or_create_pool_persists_across_calls(tmp_path):
    pool_path = tmp_path / "proto_lexicon.json"
    first = protolang.load_or_create_pool(pool_path, size=10)
    second = protolang.load_or_create_pool(pool_path, size=10)
    assert first == second
    assert len(first) == 10


def test_pool_roots_are_unique_and_shaped(tmp_path):
    pool = protolang.load_or_create_pool(tmp_path / "lex.json", size=20)
    forms = [r["form"] for r in pool]
    assert len(set(forms)) == len(forms)
    for r in pool:
        assert r["role"] in ("structural", "content")
        if r["role"] == "content":
            assert r["domain"] in protolang.DOMAINS
            assert r["pos"] in protolang.CONTENT_POS
        else:
            assert r["domain"] is None
            assert r["pos"] in protolang.STRUCTURAL_POS


def test_legacy_pool_without_pos_field_is_regenerated(tmp_path):
    pool_path = tmp_path / "lex.json"
    legacy = {"roots": [{"form": "abc", "role": "content", "domain": "trade"}]}  # no 'pos' key
    pool_path.write_text(json.dumps(legacy), encoding="utf-8")

    pool = protolang.load_or_create_pool(pool_path, size=10)
    assert len(pool) == 10
    assert all("pos" in r for r in pool)


def test_mutate_for_branch_is_deterministic():
    root = "katamu"
    branch = "soruun"
    assert protolang.mutate_for_branch(root, branch) == protolang.mutate_for_branch(root, branch)


def test_mutate_for_branch_differs_across_branches_on_average():
    # Not every root is guaranteed to change in every branch, but across many
    # roots at least some should surface differently between two branches.
    rng = random.Random(42)
    roots = [protolang._generate_root(rng) for _ in range(50)]
    diffs = sum(
        1 for r in roots
        if protolang.mutate_for_branch(r, "branch-a") != protolang.mutate_for_branch(r, "branch-b")
    )
    assert diffs > 0


def test_mutate_for_branch_never_erodes_below_two_chars():
    rng = random.Random(1)
    for _ in range(200):
        root = protolang._generate_root(rng)
        for branch in ["a", "b", "c", "d", "e"]:
            assert len(protolang.mutate_for_branch(root, branch)) >= 2


def test_choose_root_weights_structural_higher():
    pool = [
        {"form": "aa", "role": "structural", "domain": None},
        {"form": "bb", "role": "content", "domain": "trade"},
    ]
    rng = random.Random(0)
    counts = collections.Counter(
        protolang.choose_root(pool, rng)["role"] for _ in range(2000)
    )
    assert counts["structural"] > counts["content"]


def test_choose_root_reinforces_high_confidence_lexeme():
    pool = [
        {"form": "aa", "role": "content", "domain": "trade"},
        {"form": "bb", "role": "content", "domain": "trade"},
    ]
    branch = "soruun"
    # 'aa' maps to some surface form under this branch's rules; look it up so
    # the confidence entry actually keys onto the form the generator produces.
    surface_aa = protolang.mutate_for_branch("aa", branch)
    confidence_lookup = {surface_aa: 1.0}  # fully converged belief

    rng = random.Random(0)
    counts = collections.Counter(
        protolang.choose_root(pool, rng, branch=branch, confidence_lookup=confidence_lookup)["form"]
        for _ in range(2000)
    )
    assert counts["aa"] > counts["bb"]


def test_choose_root_without_confidence_lookup_is_unaffected():
    pool = [
        {"form": "aa", "role": "content", "domain": "trade"},
        {"form": "bb", "role": "content", "domain": "trade"},
    ]
    rng = random.Random(0)
    counts = collections.Counter(
        protolang.choose_root(pool, rng)["form"] for _ in range(2000)
    )
    # No feedback signal supplied -- both content roots should land roughly evenly.
    assert abs(counts["aa"] - counts["bb"]) < 200


def test_choose_discovery_content_root_mostly_matches_domain():
    root_entry = {"form": "x", "role": "content", "domain": "religious"}
    rng = random.Random(0)
    domain_lookup = {
        ctx: dom for dom, ctxs in protolang.DOMAIN_DISCOVERIES.items() for ctx in ctxs
    }
    draws = [domain_lookup[protolang.choose_discovery(root_entry, rng)] for _ in range(500)]
    match_rate = sum(1 for d in draws if d == "religious") / len(draws)
    assert match_rate > 0.6  # allow noise margin around the configured 0.8


def test_choose_discovery_structural_root_spreads_across_domains():
    root_entry = {"form": "x", "role": "structural", "domain": None}
    rng = random.Random(0)
    domain_lookup = {
        ctx: dom for dom, ctxs in protolang.DOMAIN_DISCOVERIES.items() for ctx in ctxs
    }
    draws = [domain_lookup[protolang.choose_discovery(root_entry, rng)] for _ in range(500)]
    assert len(set(draws)) == len(protolang.DOMAINS)


def test_generate_sentence_respects_word_count_bounds(tmp_path):
    pool = protolang.load_or_create_pool(tmp_path / "lex.json", size=10)
    rng = random.Random(0)
    sentence = protolang.generate_sentence(
        branch="soruun", pool=pool, min_words=2, max_words=4, rng=rng
    )
    n_words = len(sentence.split())
    assert 2 <= n_words <= 4


def test_branch_template_is_deterministic_and_valid():
    template = protolang.branch_template("soruun")
    assert template == protolang.branch_template("soruun")
    assert template in protolang.CANDIDATE_TEMPLATES


def test_choose_root_with_pos_filter_restricts_selection():
    pool = [
        {"form": "aa", "role": "content", "domain": "trade", "pos": "noun"},
        {"form": "bb", "role": "content", "domain": "trade", "pos": "verb"},
    ]
    rng = random.Random(0)
    for _ in range(20):
        assert protolang.choose_root(pool, rng, pos="noun")["form"] == "aa"


def test_choose_root_with_pos_filter_falls_back_when_no_match():
    pool = [{"form": "aa", "role": "content", "domain": "trade", "pos": "noun"}]
    rng = random.Random(0)
    # no 'verb' roots exist -- must not crash, falls back to the full pool
    result = protolang.choose_root(pool, rng, pos="verb")
    assert result["form"] == "aa"


def test_generate_sentence_follows_branch_word_order_template(monkeypatch, tmp_path):
    # This checks word ORDER against the POS template, tracing each surface
    # word back to its canonical root -- isolate it from
    # apply_micro_variation's own randomness (tested separately), which
    # would otherwise occasionally break that exact-spelling trace-back.
    monkeypatch.setattr(protolang, "apply_micro_variation", lambda form, rng=None: form)

    pool = protolang.load_or_create_pool(tmp_path / "lex.json", size=24)
    branch = "soruun"
    template = protolang.branch_template(branch)
    n_words = len(template)
    rng = random.Random(0)

    sentence = protolang.generate_sentence(
        branch=branch, pool=pool, min_words=n_words, max_words=n_words, rng=rng
    )
    words = sentence.split()
    assert len(words) == n_words

    forms_by_word = {protolang.mutate_for_branch(r["form"], branch): r for r in pool}
    for word, expected_pos in zip(words, template):
        root = forms_by_word.get(word)
        assert root is not None, f"generated word {word!r} doesn't trace back to any pool root"
        assert root["pos"] == expected_pos


# --- apply_micro_variation: irregular per-occurrence noise on top of mutate_for_branch ---

def test_apply_micro_variation_never_touches_forms_shorter_than_three():
    rng = random.Random(0)
    assert protolang.apply_micro_variation("ab", rng) == "ab"
    assert protolang.apply_micro_variation("a", rng) == "a"
    assert protolang.apply_micro_variation("", rng) == ""


def test_apply_micro_variation_respects_probability_over_many_trials():
    rng = random.Random(42)
    form = "kalatu"
    changed = sum(1 for _ in range(2000) if protolang.apply_micro_variation(form, rng) != form)
    rate = changed / 2000
    assert 0.15 < rate < 0.35  # nominal 0.25, generous tolerance for a stochastic check


def test_apply_micro_variation_produces_a_single_character_edit():
    rng = random.Random(1)
    form = "kalatu"
    for _ in range(500):
        mutated = protolang.apply_micro_variation(form, rng)
        if mutated == form:
            continue
        # insertion/deletion/substitution: length differs by at most 1, and
        # never erodes the form below 2 characters.
        assert abs(len(mutated) - len(form)) <= 1
        assert len(mutated) >= 2


def test_mutate_for_branch_stays_pure_regardless_of_micro_variation():
    # mutate_for_branch itself must never be randomized -- choose_root relies
    # on it being a pure function of (root, branch) to find the right
    # confidence-lookup key.
    assert protolang.mutate_for_branch("kalatu", "ilvath") == protolang.mutate_for_branch("kalatu", "ilvath")
