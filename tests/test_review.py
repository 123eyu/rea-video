"""Agent-as-VLM: review tasks -> answers -> fused breakdown."""
import json

from rea_video.cli import main
from rea_video.pipeline import decompose
from rea_video.vlm import VLMConfig


def test_review_roundtrip_overrides_and_reports(media, tmp_path, capsys):
    out = tmp_path / "o"
    b = decompose(media["code"], out, use_vlm=False, ocr=False, workers=1, stems=False)
    assert b["shots"][0]["base"]["label"] != "live_action"
    assert main(["review", str(out)]) == 0
    tasks = json.loads((out / "review_tasks.json").read_text(encoding="utf-8"))
    assert tasks["shots"] and "label_probs" in tasks["instructions"]
    assert (out / tasks["shots"][0]["images"]["sheet"]).is_file()
    ans = json.loads((out / "review_answers.json").read_text(encoding="utf-8"))
    first = ans["shots"][0]
    ranked = sorted(b["shots"][0]["deterministic"]["probs"].items(), key=lambda kv: -kv[1])
    second = ranked[1][0]  # a lone reader may pick the tools' runner-up (but not a label they rule out)
    first["label_probs"].update({second: 0.9, ranked[0][0]: 0.1})
    first["evidence"] = ["真实的手和厨房"]
    first["description"] = "手持拍摄厨房台面"
    ans["shots"].append({"id": "shot_999", "label_probs": {"ai_video": 1}})
    (out / "review_answers.json").write_text(json.dumps(ans, ensure_ascii=False), encoding="utf-8")
    capsys.readouterr()
    assert main(["apply-review", str(out), "--by", "tester"]) == 0
    printed = capsys.readouterr().out
    assert "shot_999" in printed and "改判" in printed
    b2 = json.loads((out / "breakdown.json").read_text(encoding="utf-8"))
    s0 = b2["shots"][0]
    assert s0["base"]["label"] == second and s0["base"]["decided_by"] == "fused_agent"
    assert any(e.startswith("[tester 看图]") for e in s0["base"]["evidence"])
    assert "tester 看图复核 1/" in b2["summary"]["vlm"]
    md = (out / "report.md").read_text(encoding="utf-8")
    assert "agent 看图融合" in md and "手持拍摄厨房台面" in md
    # unanswered shots (all-zero probs) are skipped, not applied
    assert all("review" not in r for r in b2["shots"][1:])
    # a lone reader cannot push a code-render shot to live action: it is outside the tools' top two
    if "live_action" not in (ranked[0][0], second):
        ans["shots"][0]["label_probs"] = {"live_action": 1}
        (out / "review_answers.json").write_text(json.dumps(ans, ensure_ascii=False), encoding="utf-8")
        main(["apply-review", str(out), "--by", "tester"])
        assert json.loads((out / "breakdown.json").read_text(encoding="utf-8"))["shots"][0]["base"]["label"] != "live_action"


def test_vlm_config_merges_fallback_models_on_same_endpoint(monkeypatch):
    for k in ("REA_VLM_BASE_URL", "REA_VLM_API_KEY", "REA_VLM_MODEL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("VIDEO_ANALYSIS_BASE_URL", "https://x.test/v1")
    monkeypatch.setenv("VIDEO_ANALYSIS_API_KEY", "k")
    monkeypatch.setenv("VIDEO_ANALYSIS_MODEL_NAME", "m1")
    monkeypatch.setenv("GEMINI3_BASE_URL", "https://x.test/v1/")
    monkeypatch.setenv("GEMINI3_API_KEY", "k")
    monkeypatch.setenv("GEMINI3_MODEL_NAME", "m1,m2,m3")
    assert VLMConfig.from_env().models == ["m1", "m2", "m3"]
    monkeypatch.setenv("GEMINI3_API_KEY", "other")
    assert VLMConfig.from_env().models == ["m1"]


def test_two_of_three_beat_one_confident_model():
    from rea_video.classify import LABELS, fuse

    def p(**kw):
        rest = (1 - sum(kw.values())) / (len(LABELS) - len(kw))
        return {k: kw.get(k, rest) for k in LABELS}

    det = p(ai_video=0.46, live_action=0.38)
    vlm_and_agent_avg = p(live_action=0.48, ai_video=0.39)  # VLM says live 0.85, agent says AI 0.72
    assert max(fuse(det, vlm_and_agent_avg, "dynamic").items(), key=lambda kv: kv[1])[0] == "live_action"
    out = fuse(det, vlm_and_agent_avg, "dynamic", majority="ai_video")
    assert max(out, key=out.get) == "ai_video"
    # hard constraints still win: a frozen shot is never a generated video
    frozen = fuse(p(static_hold=0.6), p(ai_video=0.9), "frozen", majority="ai_video")
    assert max(frozen, key=frozen.get) == "static_hold" or frozen["ai_video"] < 0.5


def test_split_suggestion_kept_when_valid_and_dropped_when_empty():
    from rea_video.review import _clean

    ok, err = _clean({"id": "shot_001", "label_probs": {"ai_video": 1.0},
                      "split_suggestion": {"cuts": [12.5, 40], "labels": ["code_render", "live_action"], "note": "n"}})
    assert err is None and ok["split_suggestion"]["cuts"] == [12.5, 40.0]
    assert ok["split_suggestion"]["labels"] == ["code_render", "live_action"]
    bad, err2 = _clean({"id": "shot_001", "label_probs": {"ai_video": 1.0}, "split_suggestion": {"cuts": []}})
    assert err2 is None and not bad.get("split_suggestion")


def test_split_suggestion_rejects_malformed_input_instead_of_raising():
    from rea_video.review import _clean

    base = {"id": "shot_001", "label_probs": {"ai_video": 1.0}}
    for sp in ({"cuts": "12.5"}, {"cuts": ["abc"]}, {"cuts": [1, None]}, {"cuts": [5.0], "labels": "live_action"},
               {"cuts": [3.0], "labels": ["bogus_label"]}):
        clean, err = _clean({**base, "split_suggestion": sp})
        assert clean is None and err and "split_suggestion" in err, sp
    # cuts come back sorted, labels stay as given
    ok, err = _clean({**base, "split_suggestion": {"cuts": [40, 12.5], "labels": ["code_render", "live_action", "code_render"]}})
    assert err is None and ok["split_suggestion"]["cuts"] == [12.5, 40.0]
