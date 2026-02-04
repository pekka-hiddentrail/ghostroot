# src/ghostroot/config.py
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    project_root: Path
    data_dir: Path
    artifacts_path: Path
    research_log_path: Path

    backend: str  # "ollama" or "openai" (later)
    ollama_model: str
    ollama_bin: str

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

    backend = os.getenv("GHOSTROOT_BACKEND", "ollama").strip().lower()
    ollama_model = os.getenv("OLLAMA_MODEL", "qwen3:4b").strip()
    ollama_bin = os.getenv("OLLAMA_BIN", "ollama").strip()

    return Settings(
        project_root=project_root,
        data_dir=data_dir,
        artifacts_path=artifacts_path,
        research_log_path=research_log_path,
        backend=backend,
        ollama_model=ollama_model,
        ollama_bin=ollama_bin,
    )
