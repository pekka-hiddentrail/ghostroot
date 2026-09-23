# src/ghostroot/llm.py
from __future__ import annotations

import json
import re
import time
import urllib.request
import urllib.error
from typing import Optional

_RETRY_WAIT_PATTERN = re.compile(r"try again in ([\d.]+)s")
RATE_LIMIT_MAX_RETRIES = 4
RATE_LIMIT_DEFAULT_WAIT_S = 15.0


SYSTEM_PROMPT = """You are a concise reasoning assistant.

Rules:
- Think silently. Do not show your reasoning process.
- Output only the final answer unless explicitly asked for explanation.
- If explanation is requested: max 4 bullets, no preambles, no repetition.
- Be direct and precise."""


def complete(
    prompt: str,
    *,
    backend: str,
    model: str,
    api_key: Optional[str] = None,
    system: Optional[str] = SYSTEM_PROMPT,
    max_tokens: int = 350,
    temperature: float = 0.2,
    timeout: int = 60,
) -> str:
    """
    Single entry point for calling any supported LLM backend.
    backend: "ollama", "anthropic", or "groq"
    """
    backend = backend.strip().lower()
    if backend == "anthropic":
        return _complete_anthropic(
            prompt, model=model, api_key=api_key, system=system,
            max_tokens=max_tokens, temperature=temperature, timeout=timeout,
        )
    if backend == "groq":
        return _complete_groq(
            prompt, model=model, api_key=api_key, system=system,
            max_tokens=max_tokens, temperature=temperature, timeout=timeout,
        )
    return _complete_ollama(
        prompt, model=model, system=system,
        max_tokens=max_tokens, temperature=temperature, timeout=timeout,
    )


def _retry_wait_seconds(body: str, default: float) -> float:
    """
    Providers that rate-limit by reserving tokens against the *requested*
    max_tokens ceiling (not actual usage, seen live on Groq's free tier)
    often name the exact wait in the error body -- use that instead of a
    fixed guess, which is liable to undershoot.
    """
    match = _RETRY_WAIT_PATTERN.search(body)
    if match:
        return float(match.group(1)) + 1.0  # small margin
    return default


def _post_json(url: str, payload: dict, headers: dict, timeout: int) -> dict:
    headers = {"User-Agent": "ghostroot/0.1", **headers}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    for attempt in range(1, RATE_LIMIT_MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if e.code == 429 and attempt < RATE_LIMIT_MAX_RETRIES:
                time.sleep(_retry_wait_seconds(body, RATE_LIMIT_DEFAULT_WAIT_S))
                continue
            raise RuntimeError(f"{url} HTTP error {e.code}: {body}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"{url} connection failed: {e.reason}") from e
        except TimeoutError as e:
            raise RuntimeError(f"{url} request timed out after {timeout}s") from e
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON response from {url}: {e}") from e


def _complete_ollama(
    prompt: str,
    *,
    model: str,
    system: Optional[str],
    max_tokens: int,
    temperature: float,
    timeout: int,
    base_url: str = "http://localhost:11434",
) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "system": system or "",
        "stream": False,
        "options": {
            "temperature": temperature,
            "top_p": 0.8,
            "top_k": 20,
            "repeat_penalty": 1.12,
            "num_predict": max_tokens,
            "num_ctx": 8192,
        },
        "stop": ["<|eot_id|>", "USER:", "ASSISTANT:"],
    }
    data = _post_json(f"{base_url}/api/generate", payload, {"Content-Type": "application/json"}, timeout)
    return (data.get("response") or "").strip()


def _complete_anthropic(
    prompt: str,
    *,
    model: str,
    api_key: Optional[str],
    system: Optional[str],
    max_tokens: int,
    temperature: float,
    timeout: int,
) -> str:
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")
    payload: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        payload["system"] = system
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    data = _post_json("https://api.anthropic.com/v1/messages", payload, headers, timeout)
    parts = data.get("content") or []
    return "".join(p.get("text", "") for p in parts if p.get("type") == "text").strip()


def _complete_groq(
    prompt: str,
    *,
    model: str,
    api_key: Optional[str],
    system: Optional[str],
    max_tokens: int,
    temperature: float,
    timeout: int,
) -> str:
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set")
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = {
        "model": model,
        # Groq's current catalog (gpt-oss, qwen3) is reasoning models: they spend
        # tokens on hidden reasoning before the visible answer, so low effort +
        # headroom on max_tokens is needed or short prompts come back empty.
        "max_tokens": max(max_tokens, 200),
        "reasoning_effort": "low",
        "temperature": temperature,
        "messages": messages,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    data = _post_json("https://api.groq.com/openai/v1/chat/completions", payload, headers, timeout)
    choices = data.get("choices") or []
    if not choices:
        return ""
    return (choices[0].get("message", {}).get("content") or "").strip()
