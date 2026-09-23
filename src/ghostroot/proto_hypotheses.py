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

# Confidence is a plain percentage computed from how many distinct branches
# attest a root, using the exact same evidence-based formula as
# beliefs.confidence_of() (n / (n + prior strength)): 1 branch -> 25%, 2 ->
# 40%, 3 -> 50%, 9 -> 75%. The LLM is never asked for (or allowed to assert)
# a confidence value -- discrete low/med/high labels hide how thin "low" or
# how thick "high" actually is, and a self-reported label needed capping
# anyway, which made asking for it pointless work. Branch count is treated
# here the way evidence_for is treated in beliefs.py: real evidence, not an
# opinion.
CONFIDENCE_PRIOR_STRENGTH = 3


def _confidence_from_branch_count(branch_count: int) -> float:
    return round(branch_count / (branch_count + CONFIDENCE_PRIOR_STRENGTH), 3)


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
    branches: Optional[List[str]] = None,
    pass_id: str,
) -> Dict[str, Any]:
    """
    Insert or update a proto-root hypothesis. `confidence` is always computed
    from the number of distinct branches in `branches`, never taken from the
    LLM. `prior_confidence` is set only when the computed confidence actually
    changes (so a rendered "25% -> 50%" arrow reflects real movement, i.e. a
    newly-attested branch), and clears back to None on a pass that reaffirms
    the same branch count.
    """
    key = _normalize_root(root)
    existing = store["hypotheses"].get(key)

    branch_count = len(set(branches or []))
    confidence = _confidence_from_branch_count(branch_count)

    first_seen_pass = existing["first_seen_pass"] if existing else pass_id
    prior_confidence: Optional[float] = None
    if existing and existing.get("confidence") != confidence:
        prior_confidence = existing["confidence"]

    entry = {
        "root": root,
        "gloss": gloss,
        "meaning": meaning,
        "reasoning": reasoning,
        "confidence": confidence,
        "prior_confidence": prior_confidence,
        "branches": sorted(set(branches or [])),
        "first_seen_pass": first_seen_pass,
        "last_updated_pass": pass_id,
    }
    store["hypotheses"][key] = entry
    return entry


def _format_pct(confidence: Any) -> str:
    try:
        return f"{float(confidence) * 100:.0f}%"
    except (TypeError, ValueError):
        return str(confidence)


def confidence_display(entry: Dict[str, Any]) -> str:
    prior = entry.get("prior_confidence")
    current = entry.get("confidence", 0.0)
    if prior is not None and prior != current:
        return f"{_format_pct(prior)} → {_format_pct(current)}"
    return _format_pct(current)


def _as_float(confidence: Any) -> float:
    try:
        return float(confidence)
    except (TypeError, ValueError):
        return 0.0  # tolerates legacy low/med/high strings from before this scheme


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

    entries.sort(key=lambda e: (-_as_float(e.get("confidence")), e.get("root", "")))

    lines = []
    for e in entries:
        conf = confidence_display(e)
        gloss = e.get("gloss", "")
        meaning = e.get("meaning", "")
        branch_count = len(e.get("branches") or [])
        attestation = f"{branch_count} branch(es)" if branch_count else "branch count unknown"
        lines.append(f"- **{e.get('root', '?')}** ({gloss}) — {conf} [{attestation}] — {meaning}")
    return "\n".join(lines)
