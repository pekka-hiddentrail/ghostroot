from __future__ import annotations

import random
import re
import subprocess
from typing import Any, Dict, List, Optional
import json
import urllib.request
import urllib.error


def _ollama_generate_http(model: str, prompt: str, timeout_s: int = 30) -> str:
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            # HARD caps / speed controls:
            "num_predict": 40,          # ~30 tokens max for speaker
            "temperature": 0.4,         # reduce rambling
            "stop": ["\n\n", "###"],    # stop at first newline
        },
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return (data.get("response") or "").strip()
    except (urllib.error.URLError, TimeoutError) as e:
        return f"[timeout/error] {e}"


def generate_artifact(
    *,
    ollama_bin: str,
    model: str,
    branch: str,
    artifact_id: str,
    max_words: int = 5,
    seed_context: Optional[str] = None,
) -> List[Dict[str, Any]]:
    contexts = [
        "trade receipt scratched on wood",
        "boundary marker inscription",
        "tomb offering label",
        "short prayer fragment",
        "graffiti near a dock",
        "maker's mark on a tool",
        "temple administrative archives",
        "palace record rooms",
        "scribal school tablets",
        "private household archives",
        "merchant accounting rooms",
        "city gate offices",
        "royal chancellery archives",
        "provincial governor residences",
        "law court record rooms",
        "taxation registry offices",
        "warehouse inventory stores",
        "harbor customs offices",
        "military camp headquarters",
        "frontier fort garrisons",
        "canal maintenance offices",
        "irrigation control stations",
        "agricultural estate offices",
        "workshop accounting archives",
        "priesthood ritual storerooms",
        "oracle consultation chambers",
        "healer practice archives",
        "astronomical observation records",
        "omen interpretation libraries",
        "burial chamber deposits",
        "cemetery grave goods",
        "emergency hoard caches",
        "abandoned city ruins",
        "scribal workshop remains",
        "palace construction records",
        "diplomatic correspondence caches",
        "treaty tablet deposits",
        "census enumeration records",
        "ration distribution offices",
        "labor assignment records",
        "market regulation offices",
        "city wall guardhouses",
        "temple treasury vaults",
        "road checkpoint stations",
        "river transport offices",
        "judicial appeal archives"
    ]

    context = random.choice(contexts)

    prompt = f"""
You are an extinct speaker of a daughter language called {branch}.
Output EXACTLY ONE LINE. A sentence of 2–{max_words} nonsense words/strings of varying lengths. E.g. "yhews kahca zix" or "h'u thes wyaha rere". 
The words should be evocative of the style of a {context}. No need for punctuation.
Do NOT include analysis, thinking, or explanations.
Return only the inscription text.
""".strip()

    raw = _ollama_generate_http(model, prompt, timeout_s=30)

    # Extract all words from response
    all_words = [w for w in raw.split() if w and len(w) > 1]
    
    if not all_words:
        all_words = [w for w in raw.split() if w]
    
    # Pick a random word for the single-word inscription
    if all_words:
        single_word = random.choice(all_words)
    else:
        single_word = raw.strip().split()[0] if raw.strip() else "unk"
    
    single_word = re.sub(r'^[\'"]|[\'"]$', "", single_word).strip()
    
    # Use the full response for the sentence artifact
    sentence = re.sub(r'^[\'"]|[\'"]$', "", raw).strip()
    words = [w for w in sentence.split() if w]
    if len(words) > max_words:
        sentence = " ".join(words[:max_words])

    # Return both artifacts: single word inscription and full sentence
    return [
        {
            "id": artifact_id,
            "language": branch,
            "type": "inscription",
            "text": single_word,
            "metadata": {
                "context": context,
                "gloss": "",
                "meaning": "",
                "confidence": "",
                "gloss_updated_at": None,
            },
        },
        {
            "id": f"{artifact_id}_S",
            "language": branch,
            "type": "sentence",
            "text": sentence,
            "metadata": {
                "context": context,
                "gloss": "",
                "meaning": "",
                "confidence": "",
                "gloss_updated_at": None,
            },
        },
    ]
