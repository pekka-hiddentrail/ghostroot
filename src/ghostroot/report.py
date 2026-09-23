# src/ghostroot/report.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from ghostroot import beliefs as beliefs_store
from ghostroot import proto_hypotheses as hypotheses_store

"""
Cycle-level reports, distinct from the per-pass notes in data/research_log/.

A research-log entry captures one analysis pass in isolation. A cycle report
is the "where do we stand as of cycle N" rollup: corpus size, every tracked
proto-root hypothesis, and the strongest lexeme beliefs so far -- rendered
from a fixed template (same principle as the research-log templates) so
cycle N's report is directly comparable against cycle N-1's, not just a
narrative snapshot.
"""


def _corpus_stats(artifacts: List[Dict[str, Any]]) -> Dict[str, Any]:
    per_branch: Dict[str, Dict[str, int]] = {}
    words = 0
    sentences = 0
    for a in artifacts:
        branch = a.get("language", "unknown")
        counts = per_branch.setdefault(branch, {"words": 0, "sentences": 0})
        if a.get("type") == "inscription":
            counts["words"] += 1
            words += 1
        elif a.get("type") == "sentence":
            counts["sentences"] += 1
            sentences += 1
    return {"total": len(artifacts), "words": words, "sentences": sentences, "per_branch": per_branch}


def _render_corpus_stats(stats: Dict[str, Any]) -> str:
    lines = [
        f"- **Total artifacts:** {stats['total']}",
        f"- **Words (inscriptions):** {stats['words']}",
        f"- **Sentences:** {stats['sentences']}",
        "",
        "| Branch | Words | Sentences |",
        "|--------|-------|-----------|",
    ]
    for branch, counts in sorted(stats["per_branch"].items()):
        lines.append(f"| {branch} | {counts['words']} | {counts['sentences']} |")
    return "\n".join(lines)


def _render_top_beliefs(word_beliefs: Dict[str, Any], limit: int = 15) -> str:
    rows = []
    for entry in word_beliefs.get("entries", {}).values():
        top = beliefs_store.top_interpretation(entry)
        if not top:
            continue
        word_type, bucket, conf = top
        rows.append((conf, entry["branch"], entry["form"], word_type, bucket.get("meaning", "")))

    if not rows:
        return "_No lexeme beliefs recorded yet._"

    rows.sort(key=lambda r: (-r[0], r[1], r[2]))
    lines = ["| Branch | Form | Type | Confidence | Meaning |", "|--------|------|------|------------|---------|"]
    for conf, branch, form, word_type, meaning in rows[:limit]:
        lines.append(f"| {branch} | {form} | {word_type} | {conf * 100:.0f}% | {meaning} |")
    if len(rows) > limit:
        lines.append(f"\n_(+{len(rows) - limit} more lexeme(s) tracked, not shown)_")
    return "\n".join(lines)


def render_cycle_report(
    *,
    cycle_number: int,
    artifacts: List[Dict[str, Any]],
    word_beliefs: Dict[str, Any],
    proto_hypotheses: Dict[str, Any],
) -> str:
    stats = _corpus_stats(artifacts)
    lines = [
        f"# Cycle {cycle_number} report",
        "",
        "## Corpus",
        _render_corpus_stats(stats),
        "",
        "## Proto-root Hypotheses",
        hypotheses_store.render_summary(proto_hypotheses),
        "",
        "## Top Lexeme Beliefs",
        _render_top_beliefs(word_beliefs),
        "",
    ]
    return "\n".join(lines)


def write_cycle_report(reports_dir: Path, cycle_number: int, content: str) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"cycle_{cycle_number:03d}.md"
    path.write_text(content, encoding="utf-8")
    return path
