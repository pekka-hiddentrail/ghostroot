from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional
import json
import re

from ghostroot import beliefs as beliefs_store
from ghostroot.llm import complete as ask_llm


def _extract_tokens_from_artifacts(artifacts: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    per_lang: Dict[str, List[str]] = defaultdict(list)
    for a in artifacts:
        # Skip sentence type artifacts
        if a.get('type') == 'sentence':
            continue
        lang = a.get("language", "unknown")
        text = a.get("text", "")
        if not isinstance(text, str):
            continue
        tokens = [t.lower() for t in re.findall(r"[a-zA-Zʔʼ’-]+", text)]
        per_lang[lang].extend(tokens)
    return per_lang


def update_word_beliefs(
    *,
    artifacts: List[Dict[str, Any]],
    beliefs: Dict[str, Any],
    backend: str = "ollama",
    model: str = "ghostroot-concise",
    api_key: Optional[str] = None,
    max_lexemes_per_cycle: int = 6,
) -> List[Dict[str, Any]]:
    """
    Updates the persistent word-belief store (see ghostroot.beliefs) using the
    FULL corpus history for each lexeme, not a recency window, then returns
    per-artifact metadata updates so every occurrence of a given lexeme stays
    in sync with the single interpretation the researcher currently holds for
    it -- instead of each artifact instance being glossed independently and
    potentially contradicting other occurrences of the same word.

    Mutates `beliefs` in place; caller is responsible for persisting it.

    Returns:
        List of dicts with 'artifact_id', 'meaning', 'gloss', 'confidence',
        'word_type' -- compatible with tools.update_artifact_glosses.
    """
    artifacts_by_id = {a["id"]: a for a in artifacts if a.get("id")}

    # Index every inscription occurrence, grouped by (branch, form).
    for a in artifacts:
        if a.get("type") != "inscription":
            continue
        text = a.get("text", "")
        if not isinstance(text, str) or not text.strip():
            continue
        beliefs_store.ensure_entry(
            beliefs, branch=a.get("language", "unknown"), form=text, artifact_id=a["id"]
        )

    # Prioritize lexemes that are new or still low-confidence.
    scored = []
    for key, entry in beliefs["entries"].items():
        top = beliefs_store.top_interpretation(entry)
        conf = top[2] if top else 0.0
        scored.append((conf, key, entry))
    scored.sort(key=lambda c: c[0])
    to_review = scored[:max_lexemes_per_cycle]

    if not to_review:
        return []

    lexeme_blocks = []
    for conf, key, entry in to_review:
        occs = beliefs_store.occurrences_for(entry, artifacts_by_id)
        context_list = [o.get("metadata", {}).get("discovery", "?") for o in occs]
        distinct = sorted(set(context_list))
        spread = f"{len(distinct)} distinct context(s) across {len(context_list)} occurrence(s)"
        top = beliefs_store.top_interpretation(entry)
        current = (
            f"current best guess: {top[0]} / '{top[1]['meaning']}' (confidence {top[2]:.2f})"
            if top else "no interpretation yet"
        )
        lexeme_blocks.append(
            f"- form='{entry['form']}' branch='{entry['branch']}', "
            f"seen {len(occs)}x, {spread}: {', '.join(distinct) or 'unknown'}. {current}"
        )

    prompt = f"""
You are a historical linguist. For each lexeme below you are shown EVERY
context it has appeared in across the entire corpus so far (not just recent
finds), and the current best guess if one exists.

Use the DISTRIBUTION of contexts as real evidence, the way linguists use the
distributional hypothesis: a word spread thinly across many unrelated
contexts, with no concentration, behaves like a structural/grammatical word
(article, conjunction, pronoun, particle) rather than a concrete noun or verb.
A word concentrated in one or two contexts likely has a concrete content
meaning tied to that domain. Let this distribution genuinely drive your
word_type choice, not just the context labels' literal wording.

For each lexeme, decide:
- word_type: a short grammatical/semantic role label (e.g. "article", "verb: to give", "noun: water", "unknown")
- meaning: detailed English interpretation
- gloss: 1-4 word label, or "" if not confident enough
- supports_existing: true only if this genuinely reinforces the SAME word_type as the current best guess; false if you'd classify it differently or the evidence contradicts it

Be conservative. Do not simply repeat the current guess to appear consistent --
if you'd have proposed something different from scratch, say so and set
supports_existing to false.

Lexemes:
{chr(10).join(lexeme_blocks)}

Output ONLY a JSON array, one object per lexeme:
[
  {{"form": "...", "branch": "...", "word_type": "...", "meaning": "...", "gloss": "...", "supports_existing": true}}
]
""".strip()

    # Each lexeme's answer runs ~100-150 tokens; give the array room to finish
    # instead of getting cut off mid-object and failing to parse.
    raw = ask_llm(
        prompt,
        backend=backend,
        model=model,
        api_key=api_key,
        max_tokens=max(350, 180 * len(to_review)),
    )

    try:
        proposals = json.loads(raw)
    except json.JSONDecodeError:
        proposals = []

    updates: List[Dict[str, Any]] = []
    for prop in proposals if isinstance(proposals, list) else []:
        form = prop.get("form", "")
        branch = prop.get("branch", "")
        key = beliefs_store.key_for(branch, form)
        entry = beliefs["entries"].get(key)
        if entry is None:
            continue

        # "supports_existing" only makes sense as a judgment against a PRIOR
        # interpretation. For a lexeme with no existing belief yet, a first
        # proposal can't logically contradict anything -- treat it as
        # support regardless of what the model answered, otherwise a first
        # observation can land as evidence_for=0/evidence_against=1
        # (confidence 0.0) purely from the model hedging on a fresh guess.
        had_prior_interpretation = beliefs_store.top_interpretation(entry) is not None
        supports = True if not had_prior_interpretation else bool(prop.get("supports_existing", True))

        beliefs_store.record_interpretation(
            entry,
            word_type=prop.get("word_type") or "unknown",
            meaning=prop.get("meaning", ""),
            gloss=prop.get("gloss", ""),
            supports=supports,
        )

        top = beliefs_store.top_interpretation(entry)
        if not top:
            continue
        top_word_type, top_bucket, top_conf = top
        for artifact_id in entry["artifact_ids"]:
            updates.append({
                "artifact_id": artifact_id,
                "meaning": top_bucket["meaning"],
                "gloss": top_bucket["gloss"],
                "confidence": top_conf,
                "word_type": top_word_type,
            })

    return updates


def generate_research_questions(
    *,
    artifacts: List[Dict[str, Any]],
    lang_summaries: Dict[str, Any],
    existing_questions: List[Dict[str, Any]],
    backend: str = "ollama",
    model: str = "ghostroot-concise",
    api_key: Optional[str] = None,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Generate structured research questions with proposed answers and confidence.
    Reviews ALL existing questions and attempts to answer or improve them.
    
    Returns:
        Tuple of (new_questions, updated_questions)
    """
    # Prepare existing questions summary - ALWAYS include ALL questions
    existing_q_text = ""
    if existing_questions:
        existing_q_text = "\n\nALL existing research questions to review:\n"
        for i, q in enumerate(existing_questions, 1):
            answer = q.get('proposed_answer', 'NO ANSWER YET')
            conf = q.get('confidence', 'none')
            existing_q_text += f"{i}. {q.get('question', 'N/A')}\n"
            existing_q_text += f"   Current answer: {answer}\n"
            existing_q_text += f"   Current confidence: {conf}\n"
            existing_q_text += f"   (ID: {q.get('id', '?')})\n"
    
    prompt = f"""
You are a historical linguist. Based on the evidence below:

1) Review ALL existing questions listed below:
   - For questions with low/medium confidence or no answer: try to provide better answers
   - For high-confidence questions: only update if new evidence contradicts or significantly improves the answer
   - Always prioritize questions without answers first

2) Generate 2-3 NEW research questions about the proto-language that haven't been asked yet

CRITICAL: You must review EVERY question listed. Always add ALL new questions to the JSON, even if you cannot provide answers yet.

For ANSWERS/UPDATES to existing questions, provide:
- question_id: the ID of the question being answered/updated
- proposed_answer: your answer (improved or new)
- confidence: low|medium|high (can upgrade if evidence supports it)

For NEW questions, provide:
- question: the question text
- proposed_answer: leave empty "" if you cannot answer yet
- confidence: low (always start with low for new questions)

Output TWO JSON arrays:
{{
  "answers": [{{
    "question_id": "Q123",
    "proposed_answer": "...",
    "confidence": "low|medium|high"
  }}],
  "new_questions": [{{
    "question": "...",
    "proposed_answer": "",
    "confidence": "low"
  }}]
}}

Output ONLY the JSON object. No other text.{existing_q_text}

Evidence summary:
{lang_summaries}

Recent artifacts:
{artifacts[-8:]}
""".strip()

    # Reviews every existing question each cycle, so the expected output
    # grows with the question count -- a fixed budget eventually truncates
    # again as research_questions.json grows. Scale with it, same fix as
    # the update_word_beliefs truncation bug.
    raw = ask_llm(
        prompt,
        backend=backend,
        model=model,
        api_key=api_key,
        max_tokens=max(600, 120 * len(existing_questions) + 300),
    )

    # Try to parse JSON response
    try:
        result = json.loads(raw)
        if isinstance(result, dict):
            new_questions = result.get('new_questions', [])
            answers = result.get('answers', [])
            
            # Update existing questions with answers
            updated_questions = []
            for ans in answers:
                qid = ans.get('question_id')
                for eq in existing_questions:
                    if eq.get('id') == qid:
                        eq['proposed_answer'] = ans.get('proposed_answer', '')
                        eq['confidence'] = ans.get('confidence', 'low')
                        updated_questions.append(eq)
                        break
            
            return new_questions if isinstance(new_questions, list) else [], updated_questions
        return [], []
    except json.JSONDecodeError:
        # If LLM didn't return valid JSON, return empty lists
        return [], []


def analyze_corpus(
    *,
    entry_id: str,
    artifacts: List[Dict[str, Any]],
    existing_questions: List[Dict[str, Any]],
    backend: str = "ollama",
    model: str = "ghostroot-concise",
    api_key: Optional[str] = None,
    max_hypotheses: int = 3,
) -> tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
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

Tasks:
1) Identify 2–5 possible cognate sets across descendant languages (similar-looking words).
2) Propose up to {max_hypotheses} proto-root hypotheses.
3) Note 1–3 open questions to investigate next.

Important:
- Do NOT claim certainty, only confidence
- Prefer short, structured output.

Output your findings using EXACTLY this markdown structure, in this order, with these
exact headings every time (so this report can be diffed against past passes). If a
section has nothing to report, write "_None this pass._" under it — never omit, rename,
or reorder a heading:

## Cognate Sets
1. **<form>** – <one line: which branches/artifacts it appears in>

## Proto-root Hypotheses
| Root | Gloss | Meaning | Reasoning | Confidence |
|------|-------|---------|-----------|------------|
| *root* | gloss | english meaning | brief justification | low/med/high |

## Open Questions
1. <question>

Evidence summary (token stats):
{lang_summaries}

Recent artifacts (most recent last):
{last_artifacts}
""".strip()

    # Cognate sets + up to max_hypotheses proto-root writeups + open
    # questions routinely runs past the previous 350-token default and got
    # cut off mid-sentence (visible in the saved research log).
    raw = ask_llm(prompt, backend=backend, model=model, api_key=api_key, max_tokens=900)

    # Generate structured research questions and try to answer existing ones
    new_questions, updated_questions = generate_research_questions(
        artifacts=artifacts,
        lang_summaries=lang_summaries,
        existing_questions=existing_questions,
        backend=backend,
        model=model,
        api_key=api_key,
    )

    note = {
        "id": entry_id,
        "type": "research_note",
        "summary": raw,
        "metadata": {
            "artifact_count": len(artifacts),
            "languages_seen": sorted(list(per_lang_tokens.keys())),
        },
    }

    return note, new_questions, updated_questions
