from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple
import json
import re

from ghostroot.llm import complete as ask_llm

_CONTRADICTIONS_JSON_BLOCK = re.compile(r"```json\s*(\[.*?\])\s*```", re.DOTALL)


def _extract_contradictions_json(raw: str) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Pulls the trailing fenced JSON block of per-word contradiction verdicts
    out of the report, mirroring researcher._extract_hypotheses_json. The
    prose sections are for a human to read; this is what lets a genuine
    contradiction actually register as evidence against the belief it
    disagrees with, instead of sitting in the log as unactioned narrative.
    """
    match = _CONTRADICTIONS_JSON_BLOCK.search(raw)
    if not match:
        return raw, []
    cleaned = (raw[: match.start()] + raw[match.end():]).strip()
    try:
        parsed = json.loads(match.group(1))
    except json.JSONDecodeError:
        return cleaned, []
    return cleaned, parsed if isinstance(parsed, list) else []


def _extract_word_contexts(artifacts: List[Dict[str, Any]]) -> Dict[Tuple[str, str], List[Dict[str, Any]]]:
    """
    Build a mapping of (branch, word) -> the contexts/sentences that word
    appears in. Keyed the same way as beliefs.key_for (branch, surface form),
    not by surface form alone -- a word contradiction found here can only be
    applied back onto the right belief-store entry if it's keyed consistently
    with it. Keying by form alone (as this used to) would silently conflate
    two different words that happen to share a spelling across branches.
    """
    word_contexts: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)

    # First, build word glosses lookup from inscription artifacts, per branch.
    word_glosses = {}
    for a in artifacts:
        if a.get('type') == 'inscription':
            word = a.get('text', '').lower().strip()
            branch = a.get('language', 'unknown')
            metadata = a.get('metadata', {})
            if word and metadata.get('meaning'):
                word_glosses[(branch, word)] = {
                    'meaning': metadata.get('meaning', ''),
                    'gloss': metadata.get('gloss', ''),
                    'confidence': metadata.get('confidence', 'none'),
                    'artifact_id': a.get('id', '?')
                }

    # Now collect sentence contexts for each (branch, word).
    for a in artifacts:
        if a.get('type') == 'sentence':
            branch = a.get('language', 'unknown')
            sentence = a.get('text', '')
            context = a.get('metadata', {}).get('discovery', 'unknown')

            tokens = [t.lower() for t in re.findall(r"[a-zA-Zʔʼ'-]+", sentence)]
            for token in tokens:
                key = (branch, token)
                if key in word_glosses:
                    word_contexts[key].append({
                        'sentence': sentence,
                        'context': context,
                        'artifact_id': a.get('id', '?'),
                        'word_gloss': word_glosses[key]
                    })

    return word_contexts


def analyze_contextual_fit(
    *,
    entry_id: str,
    artifacts: List[Dict[str, Any]],
    backend: str = "ollama",
    model: str = "ghostroot-concise",
    api_key: Optional[str] = None,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Analyze whether word interpretations fit the contexts they appear in.
    Focus on sentences and whether glosses make sense contextually.

    Returns:
        (note, contradictions) -- note is the log-entry dict; contradictions
        is a list of {"branch", "form", "note"} for words the LLM judged to
        genuinely conflict with their current gloss, ready for the caller to
        record as real evidence_against on that belief (see run.py).
    """
    word_contexts = _extract_word_contexts(artifacts)

    if not word_contexts:
        # No words with glosses appearing in sentences yet
        note = {
            "id": entry_id,
            "type": "context_analysis",
            "summary": (
                "## Observations\n_None this pass._\n\n"
                "## Contradictions\n_None this pass._\n\n"
                "## Words Needing Reinterpretation\n_None this pass._\n\n"
                "(No glossed words found in sentence contexts yet. Need more data.)"
            ),
            "metadata": {
                "words_analyzed": 0,
                "contradictions_found": 0,
            },
        }
        return note, []

    # Build analysis data
    analysis_text = []
    for (branch, word), contexts in list(word_contexts.items())[:10]:  # Limit to 10 most recent words
        gloss_info = contexts[0]['word_gloss']  # All contexts have same gloss
        context_types = [c['context'] for c in contexts]

        analysis_text.append(
            f"Word: '{word}' (branch: {branch})\n"
            f"  Gloss: {gloss_info['gloss'] or '(none)'}\n"
            f"  Meaning: {gloss_info['meaning']}\n"
            f"  Confidence: {gloss_info['confidence']}\n"
            f"  Contexts: {', '.join(set(context_types))}\n"
            f"  Example sentence: {contexts[0]['sentence']}"
        )

    analysis_data = "\n\n".join(analysis_text)

    prompt = f"""
You are a historical linguist doing contextual analysis.

Task: Analyze whether word interpretations fit the contexts they appear in.

For each word below, check:
1) Does the proposed meaning/gloss make sense in the archaeological contexts listed?
2) Are there contradictions? (e.g., "offering" appearing only in astronomical contexts)
3) Should confidence be adjusted based on context patterns?

Be concise and skeptical. Focus on problems.

Output your findings using EXACTLY this markdown structure, in this order, with these
exact headings every time (so this report can be diffed against past passes). If a
section has nothing to report, write "_None this pass._" under it — never omit, rename,
or reorder a heading:

## Observations
- <2-4 observations about contextual fit>

## Contradictions
- <clear contradictions or inconsistencies, or "_None this pass._">

## Words Needing Reinterpretation
1. <word> (branch) – <suggested reinterpretation, or "_None this pass._">

After the sections above, output a fenced ```json code block: a JSON array, one object
per word you examined, with EXACTLY these keys: "form", "branch", "contradicts_current_gloss"
(true only if the context genuinely conflicts with the current gloss -- not for mild
uncertainty), "note" (one short reason). This is parsed by code to record a genuine
contradiction as real evidence against that belief, so only mark true when you'd actually
argue the current gloss is wrong.

Data:
{analysis_data}
""".strip()

    # Up to 10 words' worth of observations + contradictions + reinterpretation
    # suggestions routinely ran past the previous 350-token default and got
    # cut off mid-sentence.
    raw = ask_llm(prompt, backend=backend, model=model, api_key=api_key, max_tokens=900)

    report, verdicts = _extract_contradictions_json(raw)

    contradictions = []
    for v in verdicts:
        if not isinstance(v, dict) or not v.get("contradicts_current_gloss"):
            continue
        form = (v.get("form") or "").strip().lower()
        branch = (v.get("branch") or "").strip()
        if form and branch:
            contradictions.append({"branch": branch, "form": form, "note": v.get("note", "")})

    note = {
        "id": entry_id,
        "type": "context_analysis",
        "summary": report,
        "metadata": {
            "words_analyzed": len(word_contexts),
            "sentence_count": sum(len(contexts) for contexts in word_contexts.values()),
            "contradictions_found": len(contradictions),
        },
    }

    return note, contradictions
