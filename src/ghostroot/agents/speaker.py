from __future__ import annotations

import random
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from ghostroot import protolang
from ghostroot.llm import complete


def generate_artifact(
    *,
    backend: str,
    model: str,
    branch: str,
    artifact_id: str,
    max_words: int = 5,
    api_key: Optional[str] = None,
    seed_discovery: Optional[str] = None,
    word_generator: str = "llm",
    lexicon_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    discoveries = [
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

    discovery = seed_discovery or random.choice(discoveries)

    if word_generator == "phonotactic":
        if lexicon_path is None:
            raise ValueError("lexicon_path is required when word_generator='phonotactic'")
        pool = protolang.load_or_create_pool(lexicon_path)
        single_word = protolang.generate_word(branch=branch, pool=pool)
        sentence = protolang.generate_sentence(branch=branch, pool=pool, max_words=max_words)
    else:
        prompt = f"""
You are an extinct speaker of a daughter language called {branch}.
Output EXACTLY ONE LINE. A sentence of 2–{max_words} nonsense words/strings of varying lengths.

IMPORTANT: Each word MUST contain at least one vowel (a, e, i, o, u), preferably 2 vowels.
Examples: "yhews kahca zix" or "h'u thes wyaha rere" or "anu beko tiras".

The words should be evocative of the style of a {discovery}. No need for punctuation.
Do NOT include analysis, thinking, or explanations.
Return only the inscription text.
""".strip()

        try:
            raw = complete(
                prompt,
                backend=backend,
                model=model,
                api_key=api_key,
                system=None,
                max_tokens=40,
                temperature=0.4,
                timeout=30,
            )
        except RuntimeError as e:
            raw = f"[error] {e}"
        raw = raw.splitlines()[0] if raw.strip() else raw

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
                "discovery": discovery,
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
                "discovery": discovery,
                "gloss": "",
                "meaning": "",
                "confidence": "",
                "gloss_updated_at": None,
            },
        },
    ]
