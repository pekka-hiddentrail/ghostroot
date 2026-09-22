# tests/test_tools.py
from __future__ import annotations

import json

import pytest

from ghostroot.tools import (
    add_artifact,
    load_artifacts,
    load_json_list,
    search_artifacts,
    update_artifact_glosses,
    write_research_log_entry,
)


def test_load_json_list_creates_file_if_missing(tmp_path):
    path = tmp_path / "missing.json"
    result = load_json_list(path)
    assert path.exists()
    assert result == []


def test_add_artifact_appends(tmp_path):
    artifacts_path = tmp_path / "artifacts.json"
    add_artifact(
        artifacts_path,
        {"id": "A1", "language": "branch_a", "type": "inscription", "text": "foo", "metadata": {}},
    )
    artifacts = load_artifacts(artifacts_path)
    assert len(artifacts) == 1
    assert artifacts[0]["id"] == "A1"


def test_write_research_log_entry_creates_one_markdown_file(tmp_path):
    log_dir = tmp_path / "research_log"
    path = write_research_log_entry(
        log_dir,
        {
            "id": "R1",
            "type": "research_note",
            "summary": "cognate found: *gubseb* across all three branches",
            "metadata": {"artifact_count": 5, "languages_seen": ["ilvath", "soruun"]},
        },
    )

    assert path == log_dir / "R1.md"
    content = path.read_text(encoding="utf-8")
    assert content.startswith("# R1")
    assert "research_note" in content
    assert "Artifact count:** 5" in content
    assert "Languages seen:** ilvath, soruun" in content
    assert "cognate found: *gubseb*" in content


def test_write_research_log_entry_creates_separate_files_per_entry(tmp_path):
    log_dir = tmp_path / "research_log"
    write_research_log_entry(log_dir, {"id": "R1", "type": "research_note", "summary": "a"})
    write_research_log_entry(log_dir, {"id": "C1", "type": "context_analysis", "summary": "b"})

    files = sorted(p.name for p in log_dir.iterdir())
    assert files == ["C1.md", "R1.md"]


def test_search_artifacts_finds_matches():
    artifacts = [
        {"id": "A1", "language": "branch_a", "type": "inscription", "text": "kar mel", "metadata": {}},
        {"id": "A2", "language": "branch_b", "type": "inscription", "text": "haru mer", "metadata": {}},
    ]
    assert [a["id"] for a in search_artifacts(artifacts, "kar")] == ["A1"]
    assert [a["id"] for a in search_artifacts(artifacts, "branch_b")] == ["A2"]


def test_invalid_json_raises(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(RuntimeError):
        load_json_list(path)


def test_update_artifact_glosses_syncs_all_matching_ids(tmp_path):
    artifacts_path = tmp_path / "artifacts.json"
    add_artifact(artifacts_path, {"id": "A1", "language": "x", "type": "inscription", "text": "foi", "metadata": {}})
    add_artifact(artifacts_path, {"id": "A2", "language": "x", "type": "inscription", "text": "foi", "metadata": {}})

    updated = update_artifact_glosses(
        artifacts_path,
        [
            {"artifact_id": "A1", "meaning": "to give", "gloss": "give", "confidence": 0.5, "word_type": "verb"},
            {"artifact_id": "A2", "meaning": "to give", "gloss": "give", "confidence": 0.5, "word_type": "verb"},
        ],
    )

    assert updated == 2
    artifacts = load_artifacts(artifacts_path)
    metas = [a["metadata"] for a in artifacts]
    assert all(m["meaning"] == "to give" for m in metas)
    assert all(m["confidence"] == 0.5 for m in metas)
    assert all(m["word_type"] == "verb" for m in metas)


def test_update_artifact_glosses_only_touches_matching_artifact(tmp_path):
    artifacts_path = tmp_path / "artifacts.json"
    add_artifact(artifacts_path, {"id": "A1", "language": "x", "type": "inscription", "text": "foi", "metadata": {}})
    add_artifact(artifacts_path, {"id": "A2", "language": "x", "type": "inscription", "text": "bar", "metadata": {}})

    update_artifact_glosses(
        artifacts_path,
        [{"artifact_id": "A1", "meaning": "m", "gloss": "g", "confidence": 0.5, "word_type": "noun"}],
    )

    artifacts = {a["id"]: a for a in load_artifacts(artifacts_path)}
    assert artifacts["A1"]["metadata"]["meaning"] == "m"
    assert artifacts["A2"]["metadata"] == {}
