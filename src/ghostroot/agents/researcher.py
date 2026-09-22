from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional
import json
import re

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


def generate_artifact_glosses(
    *,
    artifacts: List[Dict[str, Any]],
    lang_summaries: Dict[str, Any],
    backend: str = "ollama",
    model: str = "ghostroot-concise",
    api_key: Optional[str] = None,
    max_to_gloss: int = 8,
) -> List[Dict[str, Any]]:
    """
    Generate or revise glosses (interpretations) for recent artifacts.
    Prioritizes artifacts without glosses or with low confidence.
    
    Returns:
        List of dicts with 'artifact_id', 'gloss', 'confidence'
    """
    # Filter candidates: no gloss, or low confidence gloss
    candidates = []
    for a in artifacts[-20:]:  # Look at recent 20
        # Skip sentence type artifacts
        if a.get('type') == 'sentence':
            continue
        metadata = a.get('metadata', {})
        has_gloss = metadata.get('gloss') and metadata['gloss'].strip()
        confidence = metadata.get('confidence', 'none')
        if not has_gloss or confidence == 'low':
            candidates.append(a)
    
    if not candidates:
        return []
    
    # Take up to max_to_gloss
    to_gloss = candidates[-max_to_gloss:]
    
    artifacts_list = [
        f"ID: {a['id']}, Lang: {a.get('language', '?')}, Text: '{a.get('text', '')}'"
        for a in to_gloss
    ]
    artifacts_text = "\n".join(artifacts_list)
    
    prompt = f"""
You are a historical linguist. Propose interpretations for these inscriptions.

IMPORTANT RULES:
1. First determine the MEANING (detailed English interpretation)
2. Only if you have sufficient evidence, provide a GLOSS (1-4 word summary)
3. If evidence is insufficient, provide meaning but leave gloss empty

For each artifact, provide:
- artifact_id: the ID
- meaning: detailed English meaning/interpretation (REQUIRED)
- gloss: brief 1-4 word English label (ONLY if confident enough)
- confidence: low|medium|high (based on evidence strength)

Rules:
- Both meaning and gloss must be in English
- Meaning comes first, gloss only when justified
- If gloss is uncertain, leave it as empty string ""

Output a JSON array.

Discovery (language statistics):
{lang_summaries}

Artifacts to gloss:
{artifacts_text}

Example format:
[
  {{"artifact_id": "A123", "meaning": "a ceremonial water offering to deities", "gloss": "water offering", "confidence": "medium"}},
  {{"artifact_id": "A456", "meaning": "possibly indicates territorial boundary", "gloss": "", "confidence": "low"}}
]
""".strip()
    
    raw = ask_llm(prompt, backend=backend, model=model, api_key=api_key)

    try:
        glosses = json.loads(raw)
        if isinstance(glosses, list):
            return glosses
        return []
    except json.JSONDecodeError:
        return []


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

    raw = ask_llm(prompt, backend=backend, model=model, api_key=api_key)

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
) -> tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
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
2) Propose up to {max_hypotheses} proto-root hypotheses in the form: 
    * root = gloss
    * meaning = english meaning/meanings
    * reasoning: brief justification
    * confidence: low/med/high
3) Note 1–3 open questions to investigate next.

Important:
- Do NOT claim certainty, only confidence
- Prefer short, structured output.
- Use plain text with headings.

Evidence summary (token stats):
{lang_summaries}

Recent artifacts (most recent last):
{last_artifacts}
""".strip()

    raw = ask_llm(prompt, backend=backend, model=model, api_key=api_key)

    # Generate structured research questions and try to answer existing ones
    new_questions, updated_questions = generate_research_questions(
        artifacts=artifacts,
        lang_summaries=lang_summaries,
        existing_questions=existing_questions,
        backend=backend,
        model=model,
        api_key=api_key,
    )

    # Generate/update artifact glosses
    glosses = generate_artifact_glosses(
        artifacts=artifacts,
        lang_summaries=lang_summaries,
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
    
    return note, new_questions, updated_questions, glosses
