# tests/test_llm.py
from __future__ import annotations

import json
import urllib.error
from unittest.mock import patch, MagicMock

from ghostroot import llm


def test_retry_wait_seconds_parses_provider_message():
    body = 'Rate limit reached. Please try again in 8.879999999s. Upgrade for more.'
    assert llm._retry_wait_seconds(body, default=99.0) == 9.879999999


def test_retry_wait_seconds_falls_back_to_default_when_unparseable():
    assert llm._retry_wait_seconds("some other error entirely", default=12.0) == 12.0


def _http_error(code: int, body: bytes) -> urllib.error.HTTPError:
    err = urllib.error.HTTPError(url="http://x", code=code, msg="err", hdrs=None, fp=None)
    err.read = lambda: body
    return err


def test_post_json_retries_on_429_then_succeeds(monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)  # don't actually wait in tests

    success_body = json.dumps({"ok": True}).encode("utf-8")
    call_count = {"n": 0}

    def fake_urlopen(req, timeout):
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise _http_error(429, b'{"error": "rate limited, try again in 0.01s"}')
        cm = MagicMock()
        cm.__enter__.return_value.read.return_value = success_body
        return cm

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        result = llm._post_json("http://x", {"a": 1}, {}, timeout=5)

    assert result == {"ok": True}
    assert call_count["n"] == 3


def test_post_json_gives_up_after_max_retries(monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)

    def fake_urlopen(req, timeout):
        raise _http_error(429, b'{"error": "always rate limited"}')

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        try:
            llm._post_json("http://x", {"a": 1}, {}, timeout=5)
            assert False, "expected RuntimeError"
        except RuntimeError as e:
            assert "429" in str(e)


def test_post_json_does_not_retry_non_429_errors(monkeypatch):
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    call_count = {"n": 0}

    def fake_urlopen(req, timeout):
        call_count["n"] += 1
        raise _http_error(500, b'{"error": "server error"}')

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        try:
            llm._post_json("http://x", {"a": 1}, {}, timeout=5)
            assert False, "expected RuntimeError"
        except RuntimeError:
            pass

    assert call_count["n"] == 1  # no retry for a non-429 error
