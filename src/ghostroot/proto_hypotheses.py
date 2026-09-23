# src/ghostroot/proto_hypotheses.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

# Cross-branch proto-root hypotheses proposed by analyze_corpus are otherwise
# regenerated from scratch each pass (the LLM sees a recency window, not its
# own prior conclusions), so a hypothesis raised in pass 1 silently vanishes
# from the report the moment pass 2's window doesn't happen to re-surface it
# -- even though nothing ever refuted it. This module is the persistent,
# cumulative counterpart: every hypothesis the researcher has proposed stays
# tracked here across passes, so the research note can always show "where we
# stand", not just "what came up this time".
_CONFIDENCE_RANK = {"low": 0, "med": 1, "medium": 1, "high": 2}
_RANK_TO_CONFIDENCE = {0: "low", 1: "med", 2: "high"}

# A hypothesis's confidence is capped by how many distinct branches actually
# attest it, not by how confident the LLM's wording sounds -- otherwise a
# root seen exactly once, in one branch, can get called "high" purely
# because the model phrased its reasoning assertively. This mirrors the
# evidence-based design already used for word_beliefs.py (confidence comes
# from evidence_for/evidence_against counts, never asserted directly).
_MAX_RANK_FOR_BRANCH_COUNT = {0: 0, 1: 0, 2: 1}  # 3+ branches: no cap (rank 2, "high")


def _max_rank_for_branch_count(branch_count: int) -> int:
    return _MAX_RANK_FOR_BRANCH_COUNT.get(branch_count, 2)


def _cap_confidence(confidence: str, branch_count: int) -> str:
    requested_rank = _CONFIDENCE_RANK.get((confidence or "").strip().lower(), 0)
    capped_rank = min(requested_rank, _max_rank_for_branch_count(branch_count))
    return _RANK_TO_CONFIDENCE[capped_rank]


def empty_store() -> Dict[str, Any]:
    return {"hypotheses": {}}


def load_hypotheses(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return empty_store()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return empty_store()
    if not isinstance(data, dict) or "hypotheses" not in data:
        return empty_store()
    return data


def save_hypotheses(path: Path, store: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, indent=2, ensure_ascii=False), encoding="utf-8")


def _normalize_root(root: str) -> str:
    # Best-effort key: strips notational noise (leading "*", spaces, case) so
    # the same underlying root written "*wu" vs "Wu" vs "wu" collapses to one
    # entry. It will NOT merge two passes that invent different spellings for
    # what's conceptually the same root (e.g. "dollar" then "*wu") -- that
    # requires the LLM to recognize its own prior work, which the prompt asks
    # for but can't guarantee.
    return root.strip().lower().lstrip("*").replace(" ", "")


def upsert_hypothesis(
    store: Dict[str, Any],
    *,
    root: str,
    gloss: str,
    meaning: str,
    reasoning: str,
    confidence: str,
    branches: Optional[List[str]] = None,
    pass_id: str,
) -> Dict[str, Any]:
    """
    Insert or update a proto-root hypothesis. `confidence` is capped by the
    number of distinct branches in `branches` (see _cap_confidence) before
    being stored, so the LLM's self-reported label is a ceiling suggestion,
    not the final word. `prior_confidence` is set only when the FINAL,
    capped confidence actually changes level (so a rendered "low -> med"
    arrow reflects real movement, not a repeat of the same guess), and
    clears back to None on a pass that reaffirms the same level.
    """
    key = _normalize_root(root)
    existing = store["hypotheses"].get(key)

    branch_count = len(set(branches or []))
    capped_confidence = _cap_confidence(confidence, branch_count)

    first_seen_pass = existing["first_seen_pass"] if existing else pass_id
    prior_confidence: Optional[str] = None
    if existing and existing.get("confidence") != capped_confidence:
        prior_confidence = existing["confidence"]

    entry = {
        "root": root,
        "gloss": gloss,
        "meaning": meaning,
        "reasoning": reasoning,
        "confidence": capped_confidence,
        "prior_confidence": prior_confidence,
        "branches": sorted(set(branches or [])),
        "first_seen_pass": first_seen_pass,
        "last_updated_pass": pass_id,
    }
    store["hypotheses"][key] = entry
    return entry


def confidence_display(entry: Dict[str, Any]) -> str:
    prior = entry.get("prior_confidence")
    current = entry.get("confidence", "")
    if prior and prior != current:
        return f"{prior} → {current}"
    return current


def render_summary(store: Dict[str, Any]) -> str:
    """
    Renders every currently-tracked hypothesis, sorted highest-confidence
    first, regardless of whether this pass touched it -- this is the
    cumulative "where we stand" view, distinct from any single pass's
    freshly-proposed hypotheses.
    """
    entries: List[Dict[str, Any]] = list(store.get("hypotheses", {}).values())
    if not entries:
        return "_No proto-root hypotheses tracked yet._"

    entries.sort(key=lambda e: (-_CONFIDENCE_RANK.get((e.get("confidence") or "").lower(), 0), e.get("root", "")))

    lines = []
    for e in entries:
        conf = confidence_display(e)
        gloss = e.get("gloss", "")
        meaning = e.get("meaning", "")
        branch_count = len(e.get("branches") or [])
        attestation = f"{branch_count} branch(es)" if branch_count else "branch count unknown"
        lines.append(f"- **{e.get('root', '?')}** ({gloss}) — {conf} [{attestation}] — {meaning}")
    return "\n".join(lines)
