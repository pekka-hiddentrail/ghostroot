from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional
import json
import re

from ghostroot import beliefs as beliefs_store
from ghostroot import proto_hypotheses as hypotheses_store
from ghostroot.llm import complete as ask_llm

_HYPOTHESES_JSON_BLOCK = re.compile(r"```json\s*(\[.*?\])\s*```", re.DOTALL)


def _extract_hypotheses_json(raw: str) -> tuple[str, List[Dict[str, Any]]]:
    """
    Pulls the trailing fenced JSON block of proto-root hypotheses out of the
    LLM's markdown report and returns (report_without_the_block, hypotheses).
    A markdown table is fine for a human to read once, but too unreliable to
    parse back out pass after pass -- the JSON block is what actually lets
    hypotheses persist and get confidence-tracked across passes instead of
    silently vanishing whenever a later pass's report doesn't re-mention them.
    """
    match = _HYPOTHESES_JSON_BLOCK.search(raw)
    if not match:
        return raw, []
    cleaned = (raw[: match.start()] + raw[match.end():]).strip()
    try:
        parsed = json.loads(match.group(1))
    except json.JSONDecodeError:
        return cleaned, []
    return cleaned, parsed if isinstance(parsed, list) else []


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

        proposed_type = prop.get("word_type") or "unknown"
        proposed_meaning = prop.get("meaning", "")
        proposed_gloss = prop.get("gloss", "")

        prior_top = beliefs_store.top_interpretation(entry)

        if prior_top is None:
            # Nothing to contradict yet -- a first-ever proposal can't
            # logically disagree with anything, so it's support regardless
            # of what the model answered (otherwise a first observation can
            # land as evidence_for=0/evidence_against=1, confidence 0.0,
            # purely from the model hedging on a fresh guess).
            beliefs_store.record_interpretation(
                entry, word_type=proposed_type, meaning=proposed_meaning,
                gloss=proposed_gloss, supports=True,
            )
        else:
            prior_type = prior_top[0]
            if proposed_type == prior_type:
                # Same interpretation as the current top -- reinforce or
                # contradict THAT bucket directly, per the model's own verdict.
                supports_existing = bool(prop.get("supports_existing", True))
                beliefs_store.record_interpretation(
                    entry, word_type=proposed_type, meaning=proposed_meaning,
                    gloss=proposed_gloss, supports=supports_existing,
                )
            else:
                # A genuinely different interpretation was proposed. This is
                # real evidence AGAINST the old belief -- record it there,
                # not on the new candidate's own bucket (which would instead
                # score the new idea against itself and leave the old belief
                # frozen, unfalsifiable, forever). The new candidate gets
                # evidence_for: it's a real alternative reading formed from
                # actual inspection of the evidence, not a rejected guess.
                beliefs_store.record_interpretation(
                    entry, word_type=prior_type, meaning="", supports=False,
                )
                beliefs_store.record_interpretation(
                    entry, word_type=proposed_type, meaning=proposed_meaning,
                    gloss=proposed_gloss, supports=True,
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


def analyze_corpus(
    *,
    entry_id: str,
    artifacts: List[Dict[str, Any]],
    proto_hypotheses: Optional[Dict[str, Any]] = None,
    backend: str = "ollama",
    model: str = "ghostroot-concise",
    api_key: Optional[str] = None,
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

    if proto_hypotheses is None:
        proto_hypotheses = hypotheses_store.empty_store()

    prior_entries = list(proto_hypotheses.get("hypotheses", {}).values())
    if prior_entries:
        prior_summary = "\n".join(
            f"- {e['root']} ({e.get('gloss', '')}): {e.get('meaning', '')} "
            f"[confidence: {e.get('confidence')}, branches so far: {', '.join(e.get('branches') or []) or 'none recorded'}]"
            for e in prior_entries
        )
    else:
        prior_summary = "(none yet -- this is the first pass)"

    prompt = f"""
You are a historical linguist reconstructing a lost proto-language from descendant inscriptions.
You have imperfect evidence. Be cautious and explicit about uncertainty.

Tasks:
1) Identify 2–5 possible cognate sets across descendant languages (similar-looking words).
2) Propose up to {max_hypotheses} proto-root hypotheses. Where evidence still supports a
   hypothesis you already proposed in a previous pass (listed below), REUSE its exact
   root spelling and revise its confidence rather than inventing a new label for the
   same idea. Only introduce a new root when it's genuinely a different one.
3) Note 1–3 open questions to investigate next.

Important:
- Do NOT claim certainty, only confidence
- Prefer short, structured output.

Proto-root hypotheses from previous passes (reuse these labels if still applicable):
{prior_summary}

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

After the sections above, output a fenced ```json code block containing the SAME
proto-root hypotheses (including any reused from previous passes that still hold) as a
JSON array, one object per root, with EXACTLY these keys: "root", "gloss", "meaning",
"reasoning", "confidence" (one of "low", "med", "high"), "branches" (a JSON array of
EVERY branch name where this root is actually attested as evidence -- not where you
merely suspect it might apply). Your stated confidence will be capped by code based on
how many distinct branches you list, so listing only one branch caps this hypothesis at
"low" regardless of what you write here -- do not inflate "branches" to work around
that, list only branches you have real textual evidence from. This is parsed by code to
track confidence changes across passes, so it must be valid JSON and use the same root
spellings as the table above.

Evidence summary (token stats):
{lang_summaries}

Recent artifacts (most recent last):
{last_artifacts}
""".strip()

    # Cognate sets + up to max_hypotheses proto-root writeups + open
    # questions routinely runs past the previous 350-token default and got
    # cut off mid-sentence (visible in the saved research log).
    raw = ask_llm(prompt, backend=backend, model=model, api_key=api_key, max_tokens=1100)

    report, hypothesis_updates = _extract_hypotheses_json(raw)
    for h in hypothesis_updates:
        root = (h.get("root") or "").strip()
        if not root:
            continue
        branches_raw = h.get("branches") or []
        branches = [b.strip() for b in branches_raw if isinstance(b, str) and b.strip()]
        hypotheses_store.upsert_hypothesis(
            proto_hypotheses,
            root=root,
            gloss=h.get("gloss", ""),
            meaning=h.get("meaning", ""),
            reasoning=h.get("reasoning", ""),
            confidence=(h.get("confidence") or "low").strip().lower(),
            branches=branches,
            pass_id=entry_id,
        )

    summary_section = (
        "## Summary (all hypotheses tracked so far)\n"
        f"{hypotheses_store.render_summary(proto_hypotheses)}\n\n---\n\n"
    )

    note = {
        "id": entry_id,
        "type": "research_note",
        "summary": summary_section + report,
        "metadata": {
            "artifact_count": len(artifacts),
            "languages_seen": sorted(list(per_lang_tokens.keys())),
        },
    }

    return note
