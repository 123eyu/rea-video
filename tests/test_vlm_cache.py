"""Cached answers must belong to the requested model configuration."""
import json

import pytest

from rea_video.vlm import VLMClient, VLMConfig


@pytest.mark.parametrize("change", ["model", "model_order", "endpoint", "max_tokens"])
def test_changed_request_does_not_reuse_cached_answer(tmp_path, monkeypatch, change):
    calls = []

    def post(self, model, content, max_tokens):
        calls.append((self.cfg.base_url, model, max_tokens))
        return json.dumps({"answer": len(calls)})

    monkeypatch.setattr(VLMClient, "_post", post)
    media = tmp_path / "frame.jpg"
    media.write_bytes(b"same media")
    cache = tmp_path / "cache"
    original = VLMConfig("https://first.example/v1", "test", ["first", "fallback"])
    first = VLMClient(original, cache).ask_json("describe", [(media, "image/jpeg")])
    assert first["answer"] == 1

    cfg = VLMConfig(original.base_url, original.api_key, list(original.models))
    max_tokens = 4096
    if change == "model":
        cfg.models = ["second"]
    elif change == "model_order":
        cfg.models.reverse()
    elif change == "endpoint":
        cfg.base_url = "https://second.example/v1"
    else:
        max_tokens = 8192
    client = VLMClient(cfg, cache)
    result = client.ask_json("describe", [(media, "image/jpeg")], max_tokens=max_tokens)
    assert result["answer"] == 2
    assert len(calls) == 2
    # The identical request still hits the cache, including from a new client.
    assert VLMClient(cfg, cache).ask_json("describe", [(media, "image/jpeg")], max_tokens=max_tokens) == result
    assert len(calls) == 2


def test_fallback_reordering_preserves_cache_hit(tmp_path, monkeypatch):
    calls = []

    def post(self, model, content, max_tokens):
        calls.append(model)
        if model == "down":
            raise ValueError("unavailable")
        return '{"answer": "ok"}'

    monkeypatch.setattr(VLMClient, "_post", post)
    monkeypatch.setattr("rea_video.vlm.time.sleep", lambda seconds: None)
    cfg = VLMConfig("https://first.example/v1", "test", ["down", "working"])
    client = VLMClient(cfg, tmp_path / "cache")
    result = client.ask_json("describe", [])
    assert client.models == ["working", "down"]
    assert calls == ["down", "down", "working"]
    assert client.ask_json("describe", []) == result
    assert len(calls) == 3
