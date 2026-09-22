# src/ghostroot/beliefs.py
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

"""
Persistent, corpus-wide belief state about individual lexemes.

Each lexeme is keyed by (branch, surface form) so the same string in two
different descendant languages is tracked as two separate word identities --
they may later turn out to be cognates, but that's a separate, higher-level
hypothesis, not assumed here.

Unlike data/proto_lexicon.json (the hidden ground-truth root pool the
generator reads from), this store holds nothing but emergent, evidence-based
guesses: it's the researcher's accumulating interpretation, not an answer key,
which is why it's tracked in git like the rest of the research log.
"""


def empty_store() -> Dict[str, Any]:
    return {"entries": {}}


def load_beliefs(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return empty_store()
    data = json.loads(path.read_text(encoding="utf-8"))
    if "entries" not in data:
        return empty_store()
    return data


def save_beliefs(path: Path, store: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")


def key_for(branch: str, form: str) -> str:
    return f"{branch}:{form.lower().strip()}"


def ensure_entry(store: Dict[str, Any], *, branch: str, form: str, artifact_id: str) -> Dict[str, Any]:
    """Registers an occurrence of `form` in `branch`, creating the entry if needed."""
    key = key_for(branch, form)
    entry = store["entries"].get(key)
    if entry is None:
        entry = {
            "branch": branch,
            "form": form.lower().strip(),
            "artifact_ids": [],
            "interpretations": {},
            "updated_at": int(time.time()),
        }
        store["entries"][key] = entry
    if artifact_id not in entry["artifact_ids"]:
        entry["artifact_ids"].append(artifact_id)
    return entry


def record_interpretation(
    entry: Dict[str, Any],
    *,
    word_type: str,
    meaning: str,
    gloss: str = "",
    supports: bool = True,
) -> None:
    """
    Adds evidence for (or against) a candidate word_type interpretation.
    Confidence is derived from accumulated evidence, not asserted directly --
    see confidence_of().
    """
    interpretations = entry.setdefault("interpretations", {})
    bucket = interpretations.setdefault(
        word_type,
        {"meaning": meaning, "gloss": gloss, "evidence_for": 0, "evidence_against": 0},
    )
    if supports:
        bucket["evidence_for"] += 1
        bucket["meaning"] = meaning or bucket["meaning"]
        bucket["gloss"] = gloss or bucket["gloss"]
    else:
        bucket["evidence_against"] += 1
    entry["updated_at"] = int(time.time())


def confidence_of(bucket: Dict[str, Any]) -> float:
    evidence_for = bucket.get("evidence_for", 0)
    evidence_against = bucket.get("evidence_against", 0)
    return round(evidence_for / (evidence_for + evidence_against + 1), 3)


def top_interpretation(entry: Dict[str, Any]) -> Optional[Tuple[str, Dict[str, Any], float]]:
    best: Optional[Tuple[str, Dict[str, Any], float]] = None
    for word_type, bucket in entry.get("interpretations", {}).items():
        conf = confidence_of(bucket)
        if best is None or conf > best[2]:
            best = (word_type, bucket, conf)
    return best


def occurrences_for(entry: Dict[str, Any], artifacts_by_id: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Every known artifact this lexeme has appeared in, across the whole corpus."""
    return [artifacts_by_id[aid] for aid in entry.get("artifact_ids", []) if aid in artifacts_by_id]


def confidence_lookup(store: Dict[str, Any], branch: str) -> Dict[str, float]:
    """
    Maps surface form -> top interpretation confidence, for one branch.

    This is the feedback-loop hook: the generator reweights root selection
    using these confidences (see protolang.choose_root), so words the
    researcher has actually converged on get reused more, instead of the
    corpus drifting through equally-likely fresh nonsense forever.
    """
    lookup: Dict[str, float] = {}
    for entry in store.get("entries", {}).values():
        if entry.get("branch") != branch:
            continue
        top = top_interpretation(entry)
        if top:
            lookup[entry["form"]] = top[2]
    return lookup
