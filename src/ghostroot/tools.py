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


def append_research_question(questions_path: Path, question: Dict[str, Any]) -> None:
    questions = load_json_list(questions_path)
    questions.append(question)
    write_json_list(questions_path, questions)


def load_research_questions(questions_path: Path) -> List[Dict[str, Any]]:
    """Load all research questions from JSON file."""
    return load_json_list(questions_path)


def update_research_questions(
    questions_path: Path,
    question_updates: List[Dict[str, Any]]
) -> int:
    """
    Update existing research questions with new answers or confidence.
    
    Args:
        questions_path: Path to research_questions.json
        question_updates: List of updated question dicts with 'id' field
        
    Returns:
        Number of questions updated
    """
    questions = load_json_list(questions_path)
    
    # Build lookup for updates by ID
    updates_by_id = {u['id']: u for u in question_updates if 'id' in u}
    
    updated_count = 0
    for question in questions:
        qid = question.get('id')
        if qid in updates_by_id:
            update = updates_by_id[qid]
            # Update fields
            if 'proposed_answer' in update:
                question['proposed_answer'] = update['proposed_answer']
            if 'confidence' in update:
                question['confidence'] = update['confidence']
            question['updated_at'] = int(time.time())
            updated_count += 1
    
    write_json_list(questions_path, questions)
    return updated_count


def update_artifact_glosses(
    artifacts_path: Path,
    gloss_updates: List[Dict[str, Any]]
) -> int:
    """
    Update artifacts with new gloss interpretations.
    
    Args:
        artifacts_path: Path to artifacts.json
        gloss_updates: List of dicts with 'artifact_id', 'gloss', 'confidence'
        
    Returns:
        Number of artifacts updated
    """
    artifacts = load_json_list(artifacts_path)
    
    # Build lookup for updates
    updates_by_id = {u['artifact_id']: u for u in gloss_updates}
    
    updated_count = 0
    for artifact in artifacts:
        aid = artifact.get('id')
        if aid in updates_by_id:
            update = updates_by_id[aid]
            if 'metadata' not in artifact:
                artifact['metadata'] = {}
            artifact['metadata']['gloss'] = update['gloss']
            artifact['metadata']['confidence'] = update['confidence']
            artifact['metadata']['gloss_updated_at'] = int(time.time())
            updated_count += 1
    
    write_json_list(artifacts_path, artifacts)
    return updated_count


def make_id(prefix: str) -> str:
    """
    Generates a short unique-ish id for artifacts/log entries.
    Good enough for a PoC.
    """
    return f"{prefix}{int(time.time() * 1000)}"
