# src/ghostroot/tools.py
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


def _ensure_json_list_file(path: Path) -> None:
    """
    Ensures the JSON file exists and contains a JSON list.
    Creates parent directories as needed.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("[]", encoding="utf-8")
        return

    # Validate it is a list; if invalid JSON, raise clearly.
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON in {path}: {e}") from e

    if not isinstance(data, list):
        raise RuntimeError(f"Expected JSON list in {path}, got {type(data).__name__}")


def load_json_list(path: Path) -> List[Dict[str, Any]]:
    _ensure_json_list_file(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    # defensive: ensure list of dicts
    out: List[Dict[str, Any]] = []
    for i, item in enumerate(data):
        if isinstance(item, dict):
            out.append(item)
        else:
            out.append({"_invalid_index": i, "value": item})
    return out


def write_json_list(path: Path, items: List[Dict[str, Any]]) -> None:
    _ensure_json_list_file(path)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def load_artifacts(artifacts_path: Path) -> List[Dict[str, Any]]:
    return load_json_list(artifacts_path)


def add_artifact(artifacts_path: Path, artifact: Dict[str, Any]) -> None:
    artifacts = load_json_list(artifacts_path)
    artifacts.append(artifact)
    write_json_list(artifacts_path, artifacts)


def append_research_log(research_log_path: Path, entry: Dict[str, Any]) -> None:
    log = load_json_list(research_log_path)
    log.append(entry)
    write_json_list(research_log_path, log)


def search_artifacts(
    artifacts: List[Dict[str, Any]],
    keyword: str,
    *,
    fields: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Very simple keyword search over selected fields in each artifact.
    """
    keyword_lc = keyword.lower().strip()
    if not keyword_lc:
        return []

    if fields is None:
        fields = ["id", "language", "type", "text"]

    matches: List[Dict[str, Any]] = []
    for a in artifacts:
        hay = []
        for f in fields:
            v = a.get(f)
            if isinstance(v, str):
                hay.append(v)
            elif v is not None:
                hay.append(str(v))
        joined = " ".join(hay).lower()
        if keyword_lc in joined:
            matches.append(a)
    return matches


def make_id(prefix: str) -> str:
    """
    Generates a short unique-ish id for artifacts/log entries.
    Good enough for a PoC.
    """
    return f"{prefix}{int(time.time() * 1000)}"
