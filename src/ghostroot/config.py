# src/ghostroot/config.py
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


_DEFAULT_MODELS = {
    "ollama": ("qwen2.5:1.5b", "gemma:2b"),
    "anthropic": ("claude-haiku-4-5-20251001", "claude-haiku-4-5-20251001"),
    "groq": ("openai/gpt-oss-20b", "openai/gpt-oss-120b"),
}


@dataclass(frozen=True)
class Settings:
    project_root: Path
    data_dir: Path
    artifacts_path: Path
    research_log_path: Path
    research_questions_path: Path

    backend: str  # "ollama", "anthropic", or "groq"
    speaker_model: str
    researcher_model: str
    api_key: Optional[str]
    ollama_bin: str

    word_generator: str  # "llm" or "phonotactic"
    proto_lexicon_path: Path  # hidden ground-truth root pool (gitignored)
    word_beliefs_path: Path  # researcher's emergent, evolving interpretations (tracked)
    branches: list[str]

    max_speaker_words: int = 6
    max_researcher_hypotheses: int = 3


def load_settings() -> Settings:
    """
    Loads settings from .env (if present) and establishes project-relative paths.
    Assumes this file lives at: src/ghostroot/config.py
    """
    project_root = Path(__file__).resolve().parents[2]
    load_dotenv(project_root / ".env")

    project_root = Path(__file__).resolve().parents[2]  # .../ghostroot/
    data_dir = project_root / "data"
    artifacts_path = data_dir / "artifacts.json"
    research_log_path = data_dir / "research_log.json"
    research_questions_path = data_dir / "research_questions.json"

    backend = os.getenv("GHOSTROOT_BACKEND", "ollama").strip().lower()
    if backend not in _DEFAULT_MODELS:
        backend = "ollama"

    default_speaker, default_researcher = _DEFAULT_MODELS[backend]

    # Legacy env vars still work for the ollama backend.
    legacy_speaker = os.getenv("OLLAMA_SPEAKER_MODEL") if backend == "ollama" else None
    legacy_researcher = os.getenv("OLLAMA_RESEARCHER_MODEL") if backend == "ollama" else None

    speaker_model = os.getenv(
        "GHOSTROOT_SPEAKER_MODEL", legacy_speaker or default_speaker
    ).strip()
    researcher_model = os.getenv(
        "GHOSTROOT_RESEARCHER_MODEL", legacy_researcher or default_researcher
    ).strip()

    api_key: Optional[str] = None
    if backend == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip() or None
    elif backend == "groq":
        api_key = os.getenv("GROQ_API_KEY", "").strip() or None

    ollama_bin = os.getenv("OLLAMA_BIN", "ollama").strip()

    word_generator = os.getenv("GHOSTROOT_WORD_GENERATOR", "llm").strip().lower()
    proto_lexicon_path = data_dir / "proto_lexicon.json"
    word_beliefs_path = data_dir / "word_beliefs.json"

    branches_raw = os.getenv("GHOSTROOT_BRANCHES", "ilvath,soruun,kethra")
    branches = [b.strip() for b in branches_raw.split(",") if b.strip()]

    return Settings(
        project_root=project_root,
        data_dir=data_dir,
        artifacts_path=artifacts_path,
        research_log_path=research_log_path,
        research_questions_path=research_questions_path,
        backend=backend,
        speaker_model=speaker_model,
        researcher_model=researcher_model,
        api_key=api_key,
        ollama_bin=ollama_bin,
        word_generator=word_generator,
        proto_lexicon_path=proto_lexicon_path,
        word_beliefs_path=word_beliefs_path,
        branches=branches,
    )
