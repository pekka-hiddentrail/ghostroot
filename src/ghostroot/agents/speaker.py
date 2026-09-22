from __future__ import annotations

import random
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from ghostroot import beliefs as beliefs_store
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
    proto_lexicon_path: Optional[Path] = None,
    word_beliefs_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    if word_generator == "phonotactic":
        if proto_lexicon_path is None:
            raise ValueError("proto_lexicon_path is required when word_generator='phonotactic'")
        pool = protolang.load_or_create_pool(proto_lexicon_path)

        # Feedback loop: words the researcher has already converged on get
        # reused more, instead of the corpus drifting through equally-likely
        # fresh nonsense forever. No-op if there's no belief store yet.
        confidence_lookup = None
        if word_beliefs_path is not None:
            store = beliefs_store.load_beliefs(word_beliefs_path)
            confidence_lookup = beliefs_store.confidence_lookup(store, branch)

        # The inscription's root decides the discovery context (structural
        # roots scatter across all contexts, content roots mostly stay in
        # their hidden domain) so context isn't just decoration -- it's weak,
        # noisy evidence tied to what actually generated the word.
        root_entry = protolang.choose_root(pool, branch=branch, confidence_lookup=confidence_lookup)
        single_word = protolang.mutate_for_branch(root_entry["form"], branch)
        discovery = seed_discovery or protolang.choose_discovery(root_entry)
        sentence = protolang.generate_sentence(
            branch=branch, pool=pool, max_words=max_words, confidence_lookup=confidence_lookup
        )
    else:
        discovery = seed_discovery or random.choice(protolang.ALL_DISCOVERIES)
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
