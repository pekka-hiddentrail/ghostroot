from __future__ import annotations

import random
import re
import subprocess
from typing import Any, Dict, Optional


def _ollama_generate(ollama_bin: str, model: str, prompt: str) -> str:
    p = subprocess.run(
        [ollama_bin, "run", model],
        input=prompt,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if p.returncode != 0:
        raise RuntimeError(f"Ollama failed: {p.stderr.strip()}")
    return p.stdout.strip()


def generate_artifact(
    *,
    ollama_bin: str,
    model: str,
    branch: str,
    artifact_id: str,
    max_words: int = 6,
    seed_context: Optional[str] = None,
) -> Dict[str, Any]:
    contexts = [
        "trade receipt scratched on wood",
        "boundary marker inscription",
        "tomb offering label",
        "short prayer fragment",
        "graffiti near a dock",
        "maker's mark on a tool",
    ]
    context = seed_context or random.choice(contexts)

    prompt = f"""
You are an extinct speaker of a daughter language called {branch}.
Write ONE short inscription of {max_words} words or fewer.

Rules:
- Output ONLY the inscription text (no quotes, no explanations, no extra lines).
- Use simple syllables; avoid modern punctuation.
- Keep it plausible as a fragment found by archaeologists.
Context: {context}
""".strip()

    raw = _ollama_generate(ollama_bin, model, prompt)

    line = raw.splitlines()[0].strip()
    line = re.sub(r'^[\'"]|[\'"]$', "", line).strip()

    words = [w for w in line.split() if w]
    if len(words) > max_words:
        line = " ".join(words[:max_words])

    return {
        "id": artifact_id,
        "language": branch,
        "type": "inscription",
        "text": line,
        "metadata": {"context": context},
    }
