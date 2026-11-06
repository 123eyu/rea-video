"""User memory: corrections fix the breakdown, persist, re-apply, and surface as hints; prefs set defaults."""
import json

import pytest
import yaml

from rea_video.cli import main
from rea_video.memory import load_corrections, patterns
from rea_video.pipeline import _vlm_gate, decompose


@pytest.mark.parametrize("bounds, expected", [
    ({"end": 2.0}, ["shot_001"]),
    ({"start": 2.0, "end": 4.0}, ["shot_002"]),
    ({"start": 4.0}, ["shot_003"]),
    ({}, ["shot_001", "shot_002", "shot_003"]),
    ({"shots": "2"}, ["shot_002"]),
])
def test_correction_bounds_only_modify_and_remember_selected_shots(bounds, expected):
    from rea_video.memory import correct, reapply

    def breakdown():
        return {"source": {"filename": "example.mp4", "duration": 6.0, "sha256_head": "example"},
                "shots": [{"id": f"shot_{i + 1:03d}", "start": i * 2.0, "end": (i + 1) * 2.0,
                           "duration": 2.0, "base": {"label": "live_action", "confidence": 0.8},
                           "deterministic": {"probs": {"live_action": 1.0}, "facts": {}}}
                          for i in range(3)]}

    b = breakdown()
    correct(b, label="ai_video", **bounds)
    assert [s["id"] for s in b["shots"] if "user" in s] == expected
    assert [c["shot"] for c in load_corrections()] == expected
    fresh = breakdown()
    reapply(fresh)
    assert [s["id"] for s in fresh["shots"] if "user" in s] == expected


def test_empty_end_only_correction_does_not_change_memory():
    from rea_video.memory import correct

    b = {"source": {"filename": "example.mp4", "duration": 2.0, "sha256_head": "example"},
         "shots": [{"id": "shot_001", "start": 0.0, "end": 2.0, "duration": 2.0,
                    "base": {"label": "live_action", "confidence": 0.8},
                    "deterministic": {"probs": {"live_action": 1.0}, "facts": {}}}]}
    with pytest.raises(ValueError, match="没有选中任何镜头"):
        correct(b, label="ai_video", end=0.0)
    assert "user" not in b["shots"][0]
    assert load_corrections() == []


def test_correction_fixes_breakdown_and_is_remembered(media, tmp_path, capsys):
    out = tmp_path / "o"
    b = decompose(media["code"], out, use_vlm=False, ocr=False, workers=1, stems=False)
    first = b["shots"][0]["base"]["label"]
    assert first != "ai_video"
    assert main(["correct", str(out), "--shots", "1", "--label", "ai_video", "--real", "no", "--note", "这是 AI 生成的"]) == 0
    assert "已纠正 1 个镜头" in capsys.readouterr().out
    b2 = json.loads((out / "breakdown.json").read_text(encoding="utf-8"))
    s0 = b2["shots"][0]
    assert s0["base"]["label"] == "ai_video" and s0["base"]["decided_by"] == "user" and s0["base"]["confidence"] == 1.0
    assert s0["base"]["evidence"][0].startswith("[用户纠正]") and not s0["material"]["has_real_material"]
    assert "AI 生成视频" in b2["summary"]["verdict"]
    (c,) = load_corrections()
    assert c["before"] == first and c["label"] == "ai_video" and c["tool"] == first and c["note"] == "这是 AI 生成的"

    # the same file decomposed again gets the correction back
    b3 = decompose(media["code"], tmp_path / "o2", use_vlm=False, ocr=False, workers=1, stems=False)
    assert b3["shots"][0]["base"]["label"] == "ai_video"
    # ...but evaluation runs never see user corrections
    b4 = decompose(media["code"], tmp_path / "o3", use_vlm=False, ocr=False, workers=1, stems=False, memory=False)
    assert b4["shots"][0]["base"]["label"] == first

    # re-correcting the same file + shot counts once (latest wins)
    main(["correct", str(tmp_path / "o3"), "--shots", "1", "--label", "ai_video"])
    assert patterns()[0]["count"] == 1

    capsys.readouterr()
    assert main(["memory"]) == 0
    printed = capsys.readouterr().out
    assert "纠正:" in printed and "→ 用户「AI 生成视频」" in printed
    labels = tmp_path / "user_labels.yaml"
    assert main(["memory", "--export-labels", str(labels)]) == 0
    spec = yaml.safe_load(labels.read_text(encoding="utf-8"))
    assert spec["videos"][0]["segments"][0][2] == "ai_video"


def test_prefs_set_defaults_and_validate(capsys):
    assert main(["prefs", "engine", "kling2.1"]) == 0
    assert main(["prefs", "vlm", "maybe"]) == 2
    assert main(["prefs", "colour", "red"]) == 2
    assert main(["prefs", "--note", "报告尽量短"]) == 0
    capsys.readouterr()
    assert main(["prefs"]) == 0
    printed = capsys.readouterr().out
    assert "engine    = kling2.1" in printed and "说明 1: 报告尽量短" in printed
    assert main(["prefs", "engine", "--unset"]) == 0
    capsys.readouterr()
    main(["memory"])
    assert "报告尽量短" in capsys.readouterr().out


def test_single_image_reader_cannot_flip_ai_vs_live_axis():
    from rea_video.classify import LABELS

    def p(**kw):
        rest = (1 - sum(kw.values())) / (len(LABELS) - len(kw))
        return {k: kw.get(k, rest) for k in LABELS}

    def rec(det, facts=None):
        return {"deterministic": {"probs": det, "facts": facts or {}}, "vlm": {"label_probs": {}}}

    vlm_avatar = p(avatar=0.9)
    assert _vlm_gate(rec(p(ai_video=0.9, avatar=0.03)), vlm_avatar, {}) is None          # tools sure + not in top-2
    assert _vlm_gate(rec(p(ai_video=0.74, cg_3d=0.1)), p(cg_3d=0.95), {}) is None         # tools sure on AI axis
    assert _vlm_gate(rec(p(cg_3d=0.56, code_render=0.36)), p(code_render=0.8), {})        # 3D vs code: VLM helps
    assert _vlm_gate(rec(p(cg_3d=0.51, ai_video=0.18, code_render=0.12)), p(code_render=0.8), {})  # rendered subtype: reader picks
    assert _vlm_gate(rec(p(ai_video=0.3, live_action=0.25, cg_3d=0.2)), p(avatar=0.9), {}) is None  # not for generated subtypes
    assert _vlm_gate(rec(p(ai_video=0.46, live_action=0.38), {"transcode_degraded": True, "pulldown": "24→30"}),
                     p(live_action=0.85), {"native30": False}) is None                    # 24fps transcode never -> live
    assert _vlm_gate(rec(p(ai_video=0.46, live_action=0.38), {"transcode_degraded": True, "native_cadence": True}),
                     p(live_action=0.85), {"native30": False})                            # this shot has camera cadence: the reader decides
    assert _vlm_gate(rec(p(ai_video=0.46, live_action=0.38), {"transcode_degraded": True}),
                     p(live_action=0.85), {"native30": True})
    agent_only = {"deterministic": {"probs": p(ai_video=0.9, avatar=0.03), "facts": {}}, "review": {"label_probs": vlm_avatar}}
    assert _vlm_gate(agent_only, vlm_avatar, {}) is None                                 # same rule for a lone agent
    both = dict(agent_only, vlm={"label_probs": vlm_avatar})
    assert _vlm_gate(both, vlm_avatar, {}) is vlm_avatar                                 # two readers: _majority decides


def test_repeated_pattern_becomes_review_hint(media, tmp_path):
    from rea_video.memory import hint_for

    cs = [{"video_key": f"v{i}", "shot": "shot_001", "before": "cg_3d", "tool": "cg_3d", "label": "ai_video",
           "vlm": "cg_3d", "review": None, "context": {"transcoded": True}} for i in range(2)]
    (p,) = patterns(cs)
    assert p["count"] == 2 and p["vlm_wrong"] == 2 and p["transcoded"] == 2
    assert "用户过去 2 次" in hint_for("cg_3d", [p]) and hint_for("ai_video", [p]) is None
    assert hint_for("cg_3d", patterns(cs[:1])) is None  # one correction is not a pattern yet
