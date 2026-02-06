from __future__ import annotations

import json
import urllib.request
import urllib.error
from collections import defaultdict
from typing import Any, Dict, List
import re


SYSTEM_PROMPT = """You are a concise reasoning assistant.

Rules:
- Think silently. Do not show your reasoning process.
- Output only the final answer unless explicitly asked for explanation.
- If explanation is requested: max 4 bullets, no preambles, no repetition.
- Be direct and precise."""


def ask_ollama(
    prompt: str,
    model: str = "ghostroot-concise",
    base_url: str = "http://localhost:11434",
    timeout: int = 300,
) -> str:
    """
    Call Ollama HTTP API with concise generation settings.
    
    Args:
        prompt: User prompt
        model: Model name
        base_url: Ollama API base URL
        timeout: Request timeout in seconds (default: 300)
        
    Returns:
        Generated text response
        
    Raises:
        RuntimeError: On HTTP errors or timeouts
    """
    url = f"{base_url}/api/generate"
    
    payload = {
        "model": model,
        "prompt": prompt,
        "system": SYSTEM_PROMPT,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "top_p": 0.8,
            "top_k": 20,
            "repeat_penalty": 1.12,
            "num_predict": 350,
            "num_ctx": 8192,
        },
        "stop": ["<|eot_id|>", "USER:", "ASSISTANT:"],
    }
    
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        
        with urllib.request.urlopen(req, timeout=timeout) as response:
            if response.status != 200:
                raise RuntimeError(f"Ollama API returned status {response.status}")
            
            data = json.loads(response.read().decode("utf-8"))
            return data.get("response", "").strip()
            
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Ollama HTTP error {e.code}: {e.reason}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Ollama connection failed: {e.reason}") from e
    except TimeoutError as e:
        raise RuntimeError(f"Ollama request timed out after {timeout}s") from e
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON response from Ollama: {e}") from e


def _extract_word_contexts(artifacts: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Build a mapping of words to the contexts/sentences they appear in.
    Returns dict of {word: [list of context dicts with sentence, context, artifact details]}
    """
    word_contexts: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    
    # First, build word glosses lookup from inscription artifacts
    word_glosses = {}
    for a in artifacts:
        if a.get('type') == 'inscription':
            word = a.get('text', '').lower().strip()
            metadata = a.get('metadata', {})
            if word and metadata.get('meaning'):
                word_glosses[word] = {
                    'meaning': metadata.get('meaning', ''),
                    'gloss': metadata.get('gloss', ''),
                    'confidence': metadata.get('confidence', 'none'),
                    'artifact_id': a.get('id', '?')
                }
    
    # Now collect sentence contexts for each word
    for a in artifacts:
        if a.get('type') == 'sentence':
            sentence = a.get('text', '')
            context = a.get('metadata', {}).get('context', 'unknown')
            
            # Find which known words appear in this sentence
            tokens = [t.lower() for t in re.findall(r"[a-zA-Zʔʼ'-]+", sentence)]
            for token in tokens:
                if token in word_glosses:
                    word_contexts[token].append({
                        'sentence': sentence,
                        'context': context,
                        'artifact_id': a.get('id', '?'),
                        'word_gloss': word_glosses[token]
                    })
    
    return word_contexts


def analyze_contextual_fit(
    *,
    entry_id: str,
    artifacts: List[Dict[str, Any]],
    model: str = "ghostroot-concise",
) -> Dict[str, Any]:
    """
    Analyze whether word interpretations fit the contexts they appear in.
    Focus on sentences and whether glosses make sense contextually.
    
    Returns:
        Dict with analysis note containing contextual critiques and observations
    """
    word_contexts = _extract_word_contexts(artifacts)
    
    if not word_contexts:
        # No words with glosses appearing in sentences yet
        return {
            "id": entry_id,
            "type": "context_analysis",
            "summary": "No glossed words found in sentence contexts yet. Need more data.",
            "metadata": {
                "words_analyzed": 0,
                "contradictions_found": 0,
            },
        }
    
    # Build analysis data
    analysis_text = []
    for word, contexts in list(word_contexts.items())[:10]:  # Limit to 10 most recent words
        gloss_info = contexts[0]['word_gloss']  # All contexts have same gloss
        context_types = [c['context'] for c in contexts]
        
        analysis_text.append(
            f"Word: '{word}'\n"
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

Provide:
- 2-4 observations about contextual fit
- Note any clear contradictions or inconsistencies
- Suggest 1-2 words that may need reinterpretation

Be concise and skeptical. Focus on problems.

Data:
{analysis_data}
""".strip()
    
    raw = ask_ollama(prompt, model=model)
    
    note = {
        "id": entry_id,
        "type": "context_analysis",
        "summary": raw,
        "metadata": {
            "words_analyzed": len(word_contexts),
            "sentence_count": sum(len(contexts) for contexts in word_contexts.values()),
        },
    }
    
    return note
