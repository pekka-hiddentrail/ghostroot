# tests/test_report.py
from __future__ import annotations

from ghostroot import beliefs
from ghostroot import proto_hypotheses as hyp
from ghostroot import report


def _artifact(aid, branch, kind, text):
    return {"id": aid, "language": branch, "type": kind, "text": text, "metadata": {}}


def test_corpus_stats_counts_words_and_sentences_per_branch():
    artifacts = [
        _artifact("A1", "ilvath", "inscription", "foi"),
        _artifact("A1_S", "ilvath", "sentence", "foi bar"),
        _artifact("A2", "soruun", "inscription", "bar"),
    ]
    stats = report._corpus_stats(artifacts)
    assert stats["total"] == 3
    assert stats["words"] == 2
    assert stats["sentences"] == 1
    assert stats["per_branch"]["ilvath"] == {"words": 1, "sentences": 1}
    assert stats["per_branch"]["soruun"] == {"words": 1, "sentences": 0}


def test_render_top_beliefs_empty_store_says_none_recorded():
    assert report._render_top_beliefs(beliefs.empty_store()) == "_No lexeme beliefs recorded yet._"


def test_render_top_beliefs_sorts_by_confidence_descending():
    store = beliefs.empty_store()
    low = beliefs.ensure_entry(store, branch="ilvath", form="foi", artifact_id="A1")
    beliefs.record_interpretation(low, word_type="noun", meaning="water", supports=True)

    high = beliefs.ensure_entry(store, branch="soruun", form="bar", artifact_id="A2")
    for _ in range(5):
        beliefs.record_interpretation(high, word_type="noun", meaning="fire", supports=True)

    rendered = report._render_top_beliefs(store)
    assert rendered.index("bar") < rendered.index("foi")


def test_render_top_beliefs_respects_limit():
    store = beliefs.empty_store()
    for i in range(20):
        entry = beliefs.ensure_entry(store, branch="ilvath", form=f"word{i}", artifact_id=f"A{i}")
        beliefs.record_interpretation(entry, word_type="noun", meaning="x", supports=True)

    rendered = report._render_top_beliefs(store, limit=5)
    assert rendered.count("| ilvath |") == 5
    assert "more lexeme(s) tracked" in rendered


def test_render_cycle_report_includes_all_sections():
    artifacts = [_artifact("A1", "ilvath", "inscription", "foi")]
    word_beliefs = beliefs.empty_store()
    proto_hyps = hyp.empty_store()

    content = report.render_cycle_report(
        cycle_number=3, artifacts=artifacts, word_beliefs=word_beliefs, proto_hypotheses=proto_hyps,
    )

    assert "# Cycle 3 report" in content
    assert "## Corpus" in content
    assert "## Proto-root Hypotheses" in content
    assert "## Top Lexeme Beliefs" in content
    assert "_No proto-root hypotheses tracked yet._" in content
    assert "_No lexeme beliefs recorded yet._" in content


def test_write_cycle_report_creates_zero_padded_filename(tmp_path):
    reports_dir = tmp_path / "reports"
    path = report.write_cycle_report(reports_dir, 7, "# Cycle 7 report\n")
    assert path == reports_dir / "cycle_007.md"
    assert path.read_text(encoding="utf-8") == "# Cycle 7 report\n"
