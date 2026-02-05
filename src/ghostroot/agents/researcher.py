from __future__ import annotations

import subprocess
from collections import Counter, defaultdict
from typing import Any, Dict, List
import re


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


def _extract_tokens_from_artifacts(artifacts: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    per_lang: Dict[str, List[str]] = defaultdict(list)
    for a in artifacts:
        lang = a.get("language", "unknown")
        text = a.get("text", "")
        if not isinstance(text, str):
            continue
        tokens = [t.lower() for t in re.findall(r"[a-zA-Zʔʼ’-]+", text)]
        per_lang[lang].extend(tokens)
    return per_lang


def analyze_corpus(
    *,
    ollama_bin: str,
    model: str,
    entry_id: str,
    artifacts: List[Dict[str, Any]],
    max_hypotheses: int = 3,
) -> Dict[str, Any]:
    per_lang_tokens = _extract_tokens_from_artifacts(artifacts)

    lang_summaries: Dict[str, Any] = {}
    for lang, toks in per_lang_tokens.items():
        c = Counter(toks)
        lang_summaries[lang] = {
            "token_count": len(toks),
            "top_tokens": [w for w, _ in c.most_common(10)],
        }

    last_artifacts = artifacts[-12:]

    prompt = f"""
You are a historical linguist reconstructing a lost proto-language from descendant inscriptions.
You have imperfect evidence. Be cautious and explicit about uncertainty.

Output limit:
- Use maximum or 1500 words.
- 300 rows maximum.
- No rambling.

Tasks:
1) Identify 2–5 possible cognate sets across descendant languages (similar-looking words).
2) Propose up to {max_hypotheses} proto-root hypotheses in the form: *root = gloss (confidence: low/med/high)
3) Note 1–3 open questions to investigate next.

Important:
- Do NOT claim certainty.
- Prefer short, structured output.
- Use plain text with headings.

Evidence summary (token stats):
{lang_summaries}

Recent artifacts (most recent last):
{last_artifacts}
""".strip()

    raw = _ollama_generate(ollama_bin, model, prompt)

    return {
        "id": entry_id,
        "type": "research_note",
        "summary": raw,
        "metadata": {
            "artifact_count": len(artifacts),
            "languages_seen": sorted(list(per_lang_tokens.keys())),
        },
    }
