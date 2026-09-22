# tests/test_protolang.py
from __future__ import annotations

import collections
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
        else:
            assert r["domain"] is None


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
