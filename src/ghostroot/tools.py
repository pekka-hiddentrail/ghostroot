# src/ghostroot/tools.py
from __future__ import annotations

import datetime
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


def _format_metadata_line(key: str, value: Any) -> str:
    label = key.replace("_", " ").capitalize()
    if isinstance(value, list):
        value = ", ".join(str(v) for v in value)
    return f"- **{label}:** {value}"


def _timestamp_prefix_from_entry_id(entry_id: str) -> str:
    """
    make_id() embeds an epoch-millis timestamp in every id. Reuse it (rather
    than calling time.time() again here) so the filename timestamp always
    matches the moment the entry was created, and pull it into a sortable,
    human-readable prefix so the newest report in the directory listing is
    obvious without decoding epoch millis.
    """
    digits = "".join(ch for ch in entry_id if ch.isdigit())
    if not digits:
        return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    millis = int(digits)
    return datetime.datetime.fromtimestamp(
        millis / 1000, tz=datetime.timezone.utc
    ).strftime("%Y%m%dT%H%M%SZ")


def write_research_log_entry(research_log_dir: Path, entry: Dict[str, Any]) -> Path:
    """
    Writes one research-log entry as its own markdown file, instead of
    appending to one large JSON array. Each note is meant to be read as
    prose (that's what the researcher agents actually produce); a directory
    of one-file-per-entry is far easier to read and diff than a growing
    JSON blob.

    Every entry type (research_note, context_analysis) is rendered from a
    fixed section template (enforced via the LLM prompt, not parsed/validated
    here) so consecutive reports of the same type stay diffable pass-to-pass.
    The filename is timestamp-prefixed so `ls`/file explorers sort newest-last
    and the newest report is identifiable at a glance.

    Returns the path written to.
    """
    research_log_dir.mkdir(parents=True, exist_ok=True)

    entry_id = entry.get("id", "unknown")
    entry_type = entry.get("type", "note")
    metadata = entry.get("metadata", {}) or {}
    summary = entry.get("summary", "")

    lines = [f"# {entry_id} — {entry_type}", ""]
    for key, value in metadata.items():
        lines.append(_format_metadata_line(key, value))
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(summary)
    lines.append("")

    timestamp_prefix = _timestamp_prefix_from_entry_id(entry_id)
    path = research_log_dir / f"{timestamp_prefix}_{entry_id}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


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
        gloss_updates: List of dicts with 'artifact_id', 'meaning', 'gloss', 'confidence'
        
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
            # Meaning is required, gloss is optional
            artifact['metadata']['meaning'] = update.get('meaning', '')
            artifact['metadata']['gloss'] = update.get('gloss', '')
            artifact['metadata']['confidence'] = update['confidence']
            artifact['metadata']['word_type'] = update.get('word_type', '')
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
